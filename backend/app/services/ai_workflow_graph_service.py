from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, NotRequired, TypedDict

from sqlalchemy.orm import Session

from app.models.ai_task import AITask, TaskLog
from app.schemas.task_runtime import TaskStatusUpdate, TaskStepStatusUpdate
from app.services.task_runtime_service import get_task_runtime_state, set_task_runtime_state, set_task_step_runtime_state
from app.services.task_service import create_task_step
from app.services.workflow_chain_executor import _emit_tool_error_event, detect_tool_error

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional compatibility path until dependency is installed everywhere.
    END = "__end__"
    StateGraph = None

try:
    from langchain_core.tools import StructuredTool
    from langgraph.prebuilt import ToolNode
except Exception:  # pragma: no cover - optional compatibility path until dependency is installed everywhere.
    StructuredTool = None
    ToolNode = None


class WorkflowMessage(TypedDict):
    role: str
    content: str


class WorkflowToolCall(TypedDict):
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: str
    duration_ms: int
    timestamp: str
    attempts: int


class WorkflowState(TypedDict):
    messages: list[WorkflowMessage]
    project_context: dict[str, Any]
    task_output: dict[str, Any]
    tool_calls: list[WorkflowToolCall]
    next_action: str
    error_log: list[str]
    interrupted: bool
    objective: NotRequired[str]
    step_index: NotRequired[int]
    max_steps: NotRequired[int]
    plan_text: NotRequired[str]
    completed_steps: NotRequired[list[dict[str, Any]]]
    remaining_steps: NotRequired[list[dict[str, Any]]]


ToolHandler = Callable[[Session, int, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class WorkflowTool:
    name: str
    category: str
    description: str
    handler: ToolHandler


@dataclass(frozen=True)
class LangGraphToolNodeBundle:
    node: Any
    tools: list[Any]
    tool_names: list[str]
    registered: bool


def _dry_tool(tool_name: str) -> ToolHandler:
    def handler(_db: Session, _project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "mode": "dry_run",
            "tool": tool_name,
            "summary": f"{tool_name} registered and callable",
            "input_keys": sorted(payload.keys()),
        }

    return handler


def _llm_generate_tool(_db: Session, _project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.openrouter_service import generate_with_openrouter_fallback

    prompt = str(payload.get("prompt") or payload.get("objective") or "")
    if not payload.get("live_llm"):
        return {
            "mode": "dry_run",
            "summary": "llm_generate registered and traceable; live LLM disabled for this workflow run",
            "prompt_preview": prompt[:240],
        }
    if not prompt.strip():
        return {"mode": "dry_run", "summary": "No prompt supplied for llm_generate"}

    result = generate_with_openrouter_fallback(
        system_prompt=str(payload.get("system_prompt") or "You are an autonomous novel creation agent."),
        user_prompt=prompt,
        preferred_keywords=list(payload.get("model_preference") or ["qwen", "deepseek"]),
        max_model_attempts=int(payload.get("max_model_attempts") or 3),
    )
    completion = result["completion"]["choices"][0]["message"]["content"]
    return {
        "mode": "live",
        "model": result.get("model"),
        "summary": completion[:600],
        "attempts": result.get("attempts", []),
        "fallback_used": bool(result.get("fallback_used")),
    }


def _extract_entities_tool(db: Session, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    from app.schemas.entity_extraction import EntityExtractionRequest
    from app.services.entity_extraction_service import extract_entities_from_text

    text = str(payload.get("text") or payload.get("objective") or "")
    if not text.strip():
        return {"mode": "dry_run", "summary": "No text supplied for extract_entities"}
    return extract_entities_from_text(
        db,
        project_id,
        EntityExtractionRequest(
            text=text,
            source_type=str(payload.get("source_type") or "react_tool"),
            source_ref=str(payload.get("source_ref") or payload.get("iteration") or ""),
            task_id=payload.get("task_id") if isinstance(payload.get("task_id"), int) else None,
        ),
    )


def build_default_tool_registry() -> dict[str, WorkflowTool]:
    from app.services.workflow_tool_service import web_scrape_tool, web_search_tool

    tool_specs: list[tuple[str, str, str, ToolHandler]] = [
        ("web_search", "search", "Search web trend signals and author/style references.", web_search_tool),
        ("web_scrape", "search", "Scrape selected high-value web pages.", web_scrape_tool),
        ("llm_generate", "llm", "Generate or revise text through OpenRouter.", _llm_generate_tool),
        ("query_graph", "graph", "Query graph database entities and relationships.", _dry_tool("query_graph")),
        ("upsert_entity", "graph", "Insert or update graph entities after AI analysis.", _dry_tool("upsert_entity")),
        (
            "upsert_relationship",
            "graph",
            "Insert or update graph relationships after AI analysis.",
            _dry_tool("upsert_relationship"),
        ),
        ("query_sqlite", "database", "Query local business data.", _dry_tool("query_sqlite")),
        ("export_chapter_md", "file", "Export chapter final content as Markdown.", _dry_tool("export_chapter_md")),
        ("export_project_archive", "file", "Export complete project archive.", _dry_tool("export_project_archive")),
        ("extract_entities", "analysis", "Extract entities and relationships from text.", _extract_entities_tool),
        ("check_consistency", "analysis", "Check chapter consistency against project context.", _dry_tool("check_consistency")),
    ]
    return {
        name: WorkflowTool(name=name, category=category, description=description, handler=handler)
        for name, category, description, handler in tool_specs
    }


def _make_structured_tool(workflow_tool: WorkflowTool) -> Any:
    def invoke(project_id: int = 0, payload_json: str = "{}") -> str:
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Invalid payload_json: {exc}"}, ensure_ascii=False)
        output = workflow_tool.handler(None, project_id, payload)  # type: ignore[arg-type]
        return json.dumps(output, ensure_ascii=False)

    invoke.__name__ = workflow_tool.name
    invoke.__doc__ = workflow_tool.description
    return StructuredTool.from_function(
        invoke,
        name=workflow_tool.name,
        description=f"[{workflow_tool.category}] {workflow_tool.description}",
    )


def build_langgraph_tool_node(
    tool_registry: dict[str, WorkflowTool] | None = None,
) -> LangGraphToolNodeBundle:
    registry = tool_registry or build_default_tool_registry()
    if StructuredTool is None or ToolNode is None:
        return LangGraphToolNodeBundle(
            node=None,
            tools=[],
            tool_names=list(registry.keys()),
            registered=False,
        )
    tools = [_make_structured_tool(tool) for tool in registry.values()]
    return LangGraphToolNodeBundle(
        node=ToolNode(tools),
        tools=tools,
        tool_names=[tool.name for tool in registry.values()],
        registered=True,
    )


def create_initial_workflow_state(
    objective: str,
    project_context: dict[str, Any] | None = None,
    max_steps: int = 20,
) -> WorkflowState:
    return {
        "messages": [{"role": "human", "content": objective}],
        "project_context": project_context or {},
        "task_output": {},
        "tool_calls": [],
        "next_action": "THOUGHT",
        "error_log": [],
        "interrupted": False,
        "objective": objective,
        "step_index": 0,
        "max_steps": max_steps,
    }


def build_react_state_graph() -> Any:
    if StateGraph is None:
        return None

    graph = StateGraph(WorkflowState)
    graph.add_node("thought", lambda state: {**state, "next_action": "ACTION"})
    graph.add_node("action", lambda state: {**state, "next_action": "OBSERVATION"})
    graph.add_node("observation", lambda state: {**state, "next_action": "THOUGHT"})
    graph.set_entry_point("thought")
    graph.add_edge("thought", "action")
    graph.add_edge("action", "observation")
    graph.add_conditional_edges(
        "observation",
        lambda state: END if state.get("next_action") == "FINISH" else "thought",
        {"thought": "thought", END: END},
    )
    return graph.compile()


def build_plan_execute_state_graph() -> Any:
    """Compile the Planner -> Executor -> Replanner graph used by registered workflows."""
    if StateGraph is None:
        return None

    graph = StateGraph(WorkflowState)
    graph.add_node("planner", lambda state: {**state, "next_action": "EXECUTE"})
    graph.add_node("executor", lambda state: {**state, "next_action": "REPLAN"})
    graph.add_node("replanner", lambda state: {**state, "next_action": "EXECUTE"})
    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "replanner")
    graph.add_conditional_edges(
        "replanner",
        lambda state: END if not state.get("remaining_steps") or state.get("interrupted") else "executor",
        {"executor": "executor", END: END},
    )
    return graph.compile()


def _append_task_log(db: Session, task_id: int, log_type: str, message: str, payload: dict[str, Any]) -> None:
    db.add(TaskLog(task_id=task_id, log_type=log_type, message=message, payload=json.dumps(payload, ensure_ascii=False)))
    db.commit()


def _update_task_trace(db: Session, task: AITask, state: WorkflowState) -> None:
    reasoning_messages = [item for item in state["messages"] if item["role"] in {"ai", "tool"}]
    task.reasoning_trace = json.dumps(reasoning_messages, ensure_ascii=False)
    task.tool_trace = json.dumps(state["tool_calls"], ensure_ascii=False)
    task.output_payload = json.dumps(state["task_output"], ensure_ascii=False)
    if state["next_action"] == "STOPPED":
        task.status = "stopped"
    elif state["next_action"] == "PAUSED":
        task.status = "paused"
    elif state["interrupted"]:
        task.status = "interrupted"
    else:
        task.status = "completed"
    task.finished_at = datetime.now(timezone.utc)
    db.add(task)
    db.commit()
    db.refresh(task)


def _select_tool_for_iteration(iteration: int, registry: dict[str, WorkflowTool]) -> str:
    planned = ["query_sqlite", "llm_generate", "extract_entities"]
    for name in planned[iteration:]:
        if name in registry:
            return name
    return next(iter(registry))


def _check_runtime_control(db: Session, project_id: int, task_id: int, state: WorkflowState) -> bool:
    try:
        runtime = get_task_runtime_state(project_id, task_id, db)
    except TypeError:
        runtime = get_task_runtime_state(project_id, task_id)
    if runtime is None or runtime.status not in {"paused", "stopped"}:
        return False
    next_action = "PAUSED" if runtime.status == "paused" else "STOPPED"
    message = f"Runtime control requested: {runtime.status}"
    state["interrupted"] = True
    state["next_action"] = next_action
    state["messages"].append({"role": "ai", "content": message})
    _append_task_log(
        db,
        task_id,
        "control_interrupt",
        message,
        {
            "status": runtime.status,
            "current_step": runtime.current_step,
            "message": runtime.message,
        },
    )
    return True


def run_react_workflow(
    db: Session,
    project_id: int,
    task: AITask,
    objective: str,
    *,
    project_context: dict[str, Any] | None = None,
    max_steps: int = 3,
    tool_registry: dict[str, WorkflowTool] | None = None,
) -> WorkflowState:
    registry = tool_registry or build_default_tool_registry()
    state = create_initial_workflow_state(objective, project_context=project_context, max_steps=max_steps)
    task.started_at = datetime.now(timezone.utc)
    task.status = "running"
    db.add(task)
    db.commit()
    db.refresh(task)

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="running", current_step="thought", message="LangGraph-compatible ReAct started"),
    )

    for iteration in range(max_steps):
        if _check_runtime_control(db, project_id, task.id, state):
            break

        thought = f"Thought {iteration + 1}: inspect objective and choose the next autonomous tool action."
        state["messages"].append({"role": "ai", "content": thought})
        thought_step = create_task_step(
            db,
            project_id,
            task.id,
            step_no=(iteration * 3) + 1,
            step_name=f"Thought {iteration + 1}",
            step_type="reasoning",
            react_state="thought",
            status="completed",
            input_payload=objective,
        )
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=thought_step.step_no,
                step_name=thought_step.step_name,
                status="completed",
                react_state="thought",
                message=thought,
            ),
        )
        _append_task_log(db, task.id, "reasoning", thought, {"iteration": iteration + 1})

        tool_name = _select_tool_for_iteration(iteration, registry)
        tool = registry[tool_name]
        action_payload = {
            "objective": objective,
            "text": objective,
            "iteration": iteration + 1,
            "project_context": state["project_context"],
            "task_id": task.id,
        }
        action_message = f"Action {iteration + 1}: call {tool_name}."
        state["messages"].append({"role": "ai", "content": action_message})
        action_step = create_task_step(
            db,
            project_id,
            task.id,
            step_no=(iteration * 3) + 2,
            step_name=f"Action {iteration + 1}",
            step_type="action",
            react_state="action",
            status="running",
            tool_name=tool_name,
            input_payload=json.dumps(action_payload, ensure_ascii=False),
        )
        started = time.perf_counter()
        try:
            output = tool.handler(db, project_id, action_payload)
            status = "success"
        except Exception as exc:
            output = {"error": str(exc)}
            status = "failed"
            state["error_log"].append(str(exc))
        # B2 任务：探测工具结构化 error_code 并发布 tool_error 事件
        err = detect_tool_error(output)
        if err is not None:
            _emit_tool_error_event(
                task_id=task.id,
                project_id=project_id,
                tool=err["tool_name"] or tool_name,
                error_code=err["error_code"],
                remediation=err["remediation"],
                phase=tool_name,
                severity=err["severity"],
                output=output,
            )
        duration_ms = round((time.perf_counter() - started) * 1000)
        call: WorkflowToolCall = {
            "tool_name": tool_name,
            "input": action_payload,
            "output": output,
            "status": status,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        state["tool_calls"].append(call)
        _append_task_log(db, task.id, "tool_call", action_message, call)
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=action_step.step_no,
                step_name=action_step.step_name,
                status="completed" if status == "success" else "failed",
                react_state="action",
                message=f"{tool_name} {status} in {duration_ms}ms",
            ),
        )

        observation = f"Observation {iteration + 1}: {json.dumps(output, ensure_ascii=False)[:500]}"
        state["messages"].append({"role": "tool", "content": observation})
        observation_step = create_task_step(
            db,
            project_id,
            task.id,
            step_no=(iteration * 3) + 3,
            step_name=f"Observation {iteration + 1}",
            step_type="observation",
            react_state="observation",
            status="completed" if status == "success" else "failed",
            input_payload=observation,
        )
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=observation_step.step_no,
                step_name=observation_step.step_name,
                status=observation_step.status,
                react_state="observation",
                message=observation,
            ),
        )

        if status == "failed":
            state["interrupted"] = True
            state["next_action"] = "INTERRUPT"
            break

        state["task_output"][tool_name] = output
        state["step_index"] = iteration + 1
        state["next_action"] = "FINISH" if iteration + 1 >= max_steps else "THOUGHT"
        set_task_runtime_state(
            project_id,
            task.id,
            TaskStatusUpdate(
                status="running" if state["next_action"] != "FINISH" else "completed",
                current_step=state["next_action"].lower(),
                message=f"ReAct iteration {iteration + 1} completed",
            ),
        )

    _update_task_trace(db, task, state)
    final_message = "LangGraph-compatible ReAct completed"
    if state["next_action"] == "PAUSED":
        final_message = "ReAct paused by runtime control"
    elif state["next_action"] == "STOPPED":
        final_message = "ReAct stopped by runtime control"
    elif state["interrupted"]:
        final_message = "ReAct interrupted"
    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(
            status=task.status,
            current_step=state["next_action"].lower(),
            message=final_message,
        ),
    )
    return state


def _workflow_step_payload(step: dict[str, Any]) -> str:
    return json.dumps(step, ensure_ascii=False)


def _run_workflow_tool(
    db: Session,
    project_id: int,
    task: AITask,
    state: WorkflowState,
    tool: WorkflowTool,
    action_payload: dict[str, Any],
    *,
    max_attempts: int = 3,
    retry_delays: tuple[float, ...] = (2.0, 4.0, 8.0),
) -> WorkflowToolCall:
    started = time.perf_counter()
    output: dict[str, Any] = {}
    status = "failed"
    attempts = 0
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        try:
            output = tool.handler(db, project_id, action_payload)
            status = "success"
            break
        except Exception as exc:
            last_error = str(exc)
            state["error_log"].append(last_error)
            if attempt >= max_attempts:
                output = {"error": last_error}
                break
            delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)] if retry_delays else 0
            if delay > 0:
                time.sleep(delay)
    # B2 任务：探测工具结构化 error_code 并发布 tool_error 事件
    err = detect_tool_error(output)
    if err is not None:
        _emit_tool_error_event(
            task_id=task.id,
            project_id=project_id,
            tool=err["tool_name"] or tool.name,
            error_code=err["error_code"],
            remediation=err["remediation"],
            phase=tool.name,
            severity=err["severity"],
            output=output,
        )

    duration_ms = round((time.perf_counter() - started) * 1000)
    call: WorkflowToolCall = {
        "tool_name": tool.name,
        "input": action_payload,
        "output": output,
        "status": status,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
    }
    state["tool_calls"].append(call)
    _append_task_log(db, task.id, "tool_call", f"Action: call {tool.name}.", call)
    return call


def run_plan_execute_workflow(
    db: Session,
    project_id: int,
    task: AITask,
    objective: str,
    *,
    workflow_definition: dict[str, Any],
    max_steps: int = 20,
    hyperparameters: dict[str, Any] | None = None,
    tool_registry: dict[str, WorkflowTool] | None = None,
) -> WorkflowState:
    """Run a registered workflow through a traceable Planner/Executor/Replanner loop.

    This function keeps execution deterministic in tests while matching the production
    orchestration shape required by the automation spec: the Planner writes a plan,
    the Executor runs each business step through registered tools, and the Replanner
    audits whether more workflow steps remain.
    """
    registry = tool_registry or build_default_tool_registry()
    tool_node_bundle = build_langgraph_tool_node(registry)
    hyperparameters = hyperparameters or {}
    workflow_steps = list(workflow_definition.get("steps") or [])
    planned_steps = workflow_steps[: max(1, min(max_steps, len(workflow_steps) or max_steps))]
    plan_text = "\n".join(
        f"{step.get('step_no')}. {step.get('name')}: {step.get('objective')} -> {step.get('expected_output')}"
        for step in planned_steps
    )
    state = create_initial_workflow_state(
        objective,
        project_context={
            "workflow_id": workflow_definition.get("workflow_id"),
            "workflow_name": workflow_definition.get("name"),
            "dependencies": workflow_definition.get("dependencies", []),
            "output": workflow_definition.get("output"),
            "tool_node_registered": tool_node_bundle.registered,
            "registered_tools": tool_node_bundle.tool_names,
            "hyperparameters": hyperparameters,
        },
        max_steps=max_steps,
    )
    state["plan_text"] = plan_text
    state["remaining_steps"] = [dict(step) for step in planned_steps]
    state["completed_steps"] = []
    task.started_at = datetime.now(timezone.utc)
    task.status = "running"
    task.plan_text = plan_text
    db.add(task)
    db.commit()
    db.refresh(task)

    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status="running", current_step="planner", message="Planner Agent started"),
    )
    planner_message = f"Planner Agent created {len(planned_steps)} executable workflow steps."
    state["messages"].append({"role": "ai", "content": planner_message})
    create_task_step(
        db,
        project_id,
        task.id,
        step_no=1,
        step_name="Planner Agent",
        step_type="planner",
        react_state="plan",
        status="completed",
        input_payload=objective,
    )
    _append_task_log(
        db,
        task.id,
        "planner",
        planner_message,
        {
            "workflow_id": workflow_definition.get("workflow_id"),
            "plan_text": plan_text,
            "tool_node_registered": tool_node_bundle.registered,
            "registered_tools": tool_node_bundle.tool_names,
        },
    )

    next_step_no = 2
    while state["remaining_steps"]:
        if _check_runtime_control(db, project_id, task.id, state):
            break

        workflow_step = state["remaining_steps"].pop(0)
        step_name = str(workflow_step.get("name") or f"Step {workflow_step.get('step_no')}")
        previous_step_output = (
            state["completed_steps"][-1]["tool_calls"][-1]["output"]
            if state["completed_steps"] and state["completed_steps"][-1].get("tool_calls")
            else {}
        )
        thought = (
            f"Thought: execute {workflow_definition.get('workflow_id')}::{step_name}; "
            f"objective={workflow_step.get('objective')}"
        )
        state["messages"].append({"role": "ai", "content": thought})
        _append_task_log(db, task.id, "reasoning", thought, {"workflow_step": workflow_step})

        executor_step = create_task_step(
            db,
            project_id,
            task.id,
            step_no=next_step_no,
            step_name=f"Executor Agent - {step_name}",
            step_type="executor",
            react_state="action",
            status="running",
            input_payload=_workflow_step_payload(workflow_step),
        )
        set_task_runtime_state(
            project_id,
            task.id,
            TaskStatusUpdate(status="running", current_step=step_name, message=thought),
        )
        next_step_no += 1

        tool_names = [name for name in workflow_step.get("tool_hints", []) if name in registry]
        if not tool_names:
            tool_names = ["llm_generate"] if "llm_generate" in registry else [next(iter(registry))]

        step_calls: list[WorkflowToolCall] = []
        previous_tool_output: dict[str, Any] = {}
        for tool_name in tool_names:
            tool = registry[tool_name]
            action_payload = {
                "objective": objective,
                "text": objective,
                "workflow_id": workflow_definition.get("workflow_id"),
                "workflow_step": workflow_step,
                "project_context": state["project_context"],
                "task_id": task.id,
                "previous_step_output": previous_step_output,
                "previous_tool_output": previous_tool_output,
                **hyperparameters,
            }
            if "results" in previous_tool_output:
                action_payload["search_results"] = previous_tool_output["results"]
            elif "results" in previous_step_output:
                action_payload["search_results"] = previous_step_output["results"]
            state["messages"].append({"role": "ai", "content": f"Action: call {tool_name} for {step_name}."})
            call = _run_workflow_tool(db, project_id, task, state, tool, action_payload)
            step_calls.append(call)
            previous_tool_output = call["output"]
            state["messages"].append(
                {
                    "role": "tool",
                    "content": f"Observation: {tool_name} returned {call['status']} for {step_name}.",
                }
            )
            if call["status"] != "success":
                state["interrupted"] = True
                state["next_action"] = "INTERRUPT"
                break

        executor_step.status = "failed" if state["interrupted"] else "completed"
        executor_step.output_payload = json.dumps(step_calls, ensure_ascii=False)
        executor_step.finished_at = datetime.now(timezone.utc)
        db.add(executor_step)
        db.commit()
        set_task_step_runtime_state(
            project_id,
            task.id,
            TaskStepStatusUpdate(
                step_no=executor_step.step_no,
                step_name=executor_step.step_name,
                status=executor_step.status,
                react_state=executor_step.react_state,
                message=f"{len(step_calls)} tool call(s) completed for {step_name}",
            ),
        )

        completed = {
            "step": workflow_step,
            "tool_calls": step_calls,
            "status": executor_step.status,
        }
        state["completed_steps"].append(completed)
        state["task_output"][step_name] = completed
        state["step_index"] = len(state["completed_steps"])

        replan_status = "interrupted" if state["interrupted"] else "completed"
        remaining_count = len(state["remaining_steps"])
        replan_message = (
            f"Replanner Agent reviewed {step_name}; {remaining_count} step(s) remain."
            if not state["interrupted"]
            else f"Replanner Agent detected interruption at {step_name}."
        )
        state["messages"].append({"role": "ai", "content": replan_message})
        create_task_step(
            db,
            project_id,
            task.id,
            step_no=next_step_no,
            step_name=f"Replanner Agent - {step_name}",
            step_type="replanner",
            react_state="replan",
            status=replan_status,
            input_payload=json.dumps(
                {"completed_step": step_name, "remaining_steps": state["remaining_steps"]},
                ensure_ascii=False,
            ),
        )
        _append_task_log(
            db,
            task.id,
            "replanner",
            replan_message,
            {"completed_step": step_name, "remaining_count": remaining_count},
        )
        next_step_no += 1
        if state["interrupted"]:
            break

    if not state["interrupted"]:
        state["next_action"] = "FINISH"
    _update_task_trace(db, task, state)
    final_message = "Plan-and-Execute workflow completed"
    if state["next_action"] == "PAUSED":
        final_message = "Plan-and-Execute workflow paused by runtime control"
    elif state["next_action"] == "STOPPED":
        final_message = "Plan-and-Execute workflow stopped by runtime control"
    elif state["interrupted"]:
        final_message = "Plan-and-Execute workflow interrupted"
    set_task_runtime_state(
        project_id,
        task.id,
        TaskStatusUpdate(status=task.status, current_step=state["next_action"].lower(), message=final_message),
    )
    return state
