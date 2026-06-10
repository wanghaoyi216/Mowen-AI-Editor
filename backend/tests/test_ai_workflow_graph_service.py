import json
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.schemas.task_runtime import TaskRuntimeState, TaskStepRuntimeState
from app.services import ai_workflow_graph_service, task_runtime_service, task_service
from app.services.ai_workflow_graph_service import WorkflowTool


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db_session() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app = create_application()
app.dependency_overrides[get_db_session] = override_get_db_session
client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def install_memory_runtime(monkeypatch) -> None:
    task_states: dict[tuple[int, int], TaskRuntimeState] = {}
    step_states: dict[tuple[int, int, int], TaskStepRuntimeState] = {}

    def set_task_runtime_state(project_id, task_id, payload):
        state = TaskRuntimeState(
            project_id=project_id,
            task_id=task_id,
            status=payload.status,
            current_step=payload.current_step,
            message=payload.message,
        )
        task_states[(project_id, task_id)] = state
        return state

    def set_task_step_runtime_state(project_id, task_id, payload):
        state = TaskStepRuntimeState(
            project_id=project_id,
            task_id=task_id,
            step_no=payload.step_no,
            step_name=payload.step_name,
            status=payload.status,
            react_state=payload.react_state,
            message=payload.message,
        )
        step_states[(project_id, task_id, payload.step_no)] = state
        return state

    def get_task_runtime_state(project_id, task_id):
        return task_states.get((project_id, task_id))

    monkeypatch.setattr(task_runtime_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(task_runtime_service, "get_task_runtime_state", get_task_runtime_state)
    monkeypatch.setattr(task_runtime_service, "set_task_step_runtime_state", set_task_step_runtime_state)
    monkeypatch.setattr(task_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(task_service, "set_task_step_runtime_state", set_task_step_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "get_task_runtime_state", get_task_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "set_task_step_runtime_state", set_task_step_runtime_state)


def test_execute_react_uses_workflow_state_and_tool_trace(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)

    project_response = client.post("/api/v1/projects", json={"name": "自动编排测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/tasks/execute-react",
        json={
            "title": "LangGraph ReAct 骨架测试",
            "module_type": "workflow_orchestration",
            "objective": "检查项目上下文并产出实体提取计划",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    task = payload["task"]
    steps = payload["steps"]

    assert task["status"] == "completed"
    assert len(steps) == 9
    assert [step["react_state"] for step in steps[:3]] == ["thought", "action", "observation"]
    assert steps[1]["tool_name"] == "query_sqlite"

    task_response = client.get(f"/api/v1/projects/1/tasks/{task['id']}")
    persisted_task = task_response.json()["data"]
    tool_trace = json.loads(persisted_task["tool_trace"])
    reasoning_trace = json.loads(persisted_task["reasoning_trace"])

    assert [item["tool_name"] for item in tool_trace] == ["query_sqlite", "llm_generate", "extract_entities"]
    assert all(item["status"] == "success" for item in tool_trace)
    assert any("Thought 1" in item["content"] for item in reasoning_trace)


def test_default_tools_register_as_langgraph_tool_node() -> None:
    registry = ai_workflow_graph_service.build_default_tool_registry()

    bundle = ai_workflow_graph_service.build_langgraph_tool_node(registry)

    assert set(bundle.tool_names) == {
        "web_search",
        "web_scrape",
        "llm_generate",
        "query_graph",
        "upsert_entity",
        "upsert_relationship",
        "query_sqlite",
        "export_chapter_md",
        "export_project_archive",
        "extract_entities",
        "check_consistency",
    }
    assert bundle.registered is True
    assert bundle.node is not None
    assert len(bundle.tools) == 11


def test_langgraph_tool_node_has_compatible_fallback(monkeypatch) -> None:
    registry = {
        "demo_tool": WorkflowTool(
            name="demo_tool",
            category="analysis",
            description="Demo tool",
            handler=lambda _db, _project_id, payload: {"received": sorted(payload.keys())},
        )
    }
    monkeypatch.setattr(ai_workflow_graph_service, "StructuredTool", None)
    monkeypatch.setattr(ai_workflow_graph_service, "ToolNode", None)

    bundle = ai_workflow_graph_service.build_langgraph_tool_node(registry)

    assert bundle.registered is False
    assert bundle.node is None
    assert bundle.tools == []
    assert bundle.tool_names == ["demo_tool"]


def test_workflow_tool_retries_before_success(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    attempts = {"count": 0}

    def flaky_handler(_db, _project_id, _payload):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary tool failure")
        return {"ok": True}

    project_response = client.post("/api/v1/projects", json={"name": "工具重试测试"})
    assert project_response.status_code == 201

    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={
            "task_type": "retry-test",
            "module_type": "workflow_orchestration",
            "title": "Retry tool",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["data"]["id"]

    with TestingSessionLocal() as db:
        task = task_service.get_task(db, 1, task_id)
        state = ai_workflow_graph_service.create_initial_workflow_state("retry objective")
        call = ai_workflow_graph_service._run_workflow_tool(
            db,
            1,
            task,
            state,
            WorkflowTool("flaky_tool", "analysis", "Flaky tool", flaky_handler),
            {"objective": "retry objective"},
            retry_delays=(),
        )

    assert call["status"] == "success"
    assert call["attempts"] == 3
    assert call["output"] == {"ok": True}
    assert attempts["count"] == 3
    assert len(state["error_log"]) == 2


def test_workflow_tool_records_failure_after_retry_budget(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)

    project_response = client.post("/api/v1/projects", json={"name": "工具失败重试测试"})
    assert project_response.status_code == 201

    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={
            "task_type": "retry-failure-test",
            "module_type": "workflow_orchestration",
            "title": "Retry failure tool",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["data"]["id"]

    with TestingSessionLocal() as db:
        task = task_service.get_task(db, 1, task_id)
        state = ai_workflow_graph_service.create_initial_workflow_state("retry objective")
        call = ai_workflow_graph_service._run_workflow_tool(
            db,
            1,
            task,
            state,
            WorkflowTool(
                "always_fails",
                "analysis",
                "Always fails",
                lambda _db, _project_id, _payload: (_ for _ in ()).throw(RuntimeError("permanent failure")),
            ),
            {"objective": "retry objective"},
            max_attempts=2,
            retry_delays=(),
        )

    assert call["status"] == "failed"
    assert call["attempts"] == 2
    assert call["output"] == {"error": "permanent failure"}
    assert state["error_log"] == ["permanent failure", "permanent failure"]


def test_llm_generate_tool_records_model_fallback_attempts(monkeypatch) -> None:
    from app.services import openrouter_service

    def fake_generate_with_openrouter_fallback(**_kwargs):
        return {
            "model": {"id": "deepseek/deepseek-test:free"},
            "completion": {"choices": [{"message": {"content": "fallback completion"}}]},
            "attempts": [
                {"model_id": "qwen/qwen-test:free", "status": "failed", "error": "timeout"},
                {"model_id": "deepseek/deepseek-test:free", "status": "success", "error": None},
            ],
            "fallback_used": True,
        }

    monkeypatch.setattr(openrouter_service, "generate_with_openrouter_fallback", fake_generate_with_openrouter_fallback)
    registry = ai_workflow_graph_service.build_default_tool_registry()

    output = registry["llm_generate"].handler(
        None,
        1,
        {
            "live_llm": True,
            "prompt": "生成一段章节草稿",
            "model_preference": ["qwen", "deepseek"],
        },
    )

    assert output["mode"] == "live"
    assert output["model"]["id"] == "deepseek/deepseek-test:free"
    assert output["fallback_used"] is True
    assert output["attempts"][0]["status"] == "failed"
    assert output["summary"] == "fallback completion"


def test_react_stops_when_runtime_control_requests_stop(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)

    original_check = ai_workflow_graph_service._check_runtime_control

    def stop_after_first_iteration(db, project_id, task_id, state):
        if state.get("step_index") == 1:
            state["interrupted"] = True
            state["next_action"] = "STOPPED"
            state["messages"].append({"role": "ai", "content": "Runtime control requested: stopped"})
            return True
        return original_check(db, project_id, task_id, state)

    monkeypatch.setattr(ai_workflow_graph_service, "_check_runtime_control", stop_after_first_iteration)

    project_response = client.post("/api/v1/projects", json={"name": "停止控制测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/tasks/execute-react",
        json={
            "title": "Stop ReAct",
            "module_type": "workflow_orchestration",
            "objective": "角色：林岚。地点：雾城。",
        },
    )

    assert response.status_code == 200
    task = response.json()["data"]["task"]
    task_response = client.get(f"/api/v1/projects/1/tasks/{task['id']}")
    persisted_task = task_response.json()["data"]
    reasoning_trace = json.loads(persisted_task["reasoning_trace"])
    tool_trace = json.loads(persisted_task["tool_trace"])

    assert persisted_task["status"] == "stopped"
    assert len(tool_trace) == 1
    assert any("stopped" in item["content"] for item in reasoning_trace)
