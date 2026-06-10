from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.schemas.ai_task import AITaskCreate
from app.schemas.workflow_orchestration import WorkflowExecuteRequest
from app.services.ai_workflow_graph_service import run_plan_execute_workflow
from app.services.task_service import create_task, get_task_by_workflow_execution_id, list_task_steps
from app.services.workflow_log_service import write_workflow_execution_log


@dataclass(frozen=True)
class WorkflowStepDefinition:
    step_no: int
    name: str
    objective: str
    expected_output: str
    tool_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    name: str
    trigger: str
    description: str
    dependencies: list[str]
    output: str
    steps: list[WorkflowStepDefinition]


WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "wf-01": WorkflowDefinition(
        workflow_id="wf-01",
        name="热点发现与灵感生成",
        trigger="项目创建后或人类手动触发",
        description="Planner 规划搜索策略，AI 搜索、抓取、分析热点并生成灵感报告。",
        dependencies=[],
        output="灵感报告 -> worldbook 条目",
        steps=[
            WorkflowStepDefinition(1, "Plan", "规划搜索平台、关键词组合和分析维度", "搜索策略", ["llm_generate"]),
            WorkflowStepDefinition(2, "Search", "自主决定关键词并搜索热点小说信号", "搜索结果", ["web_search"]),
            WorkflowStepDefinition(3, "Scrape", "选择高价值页面并抓取内容", "页面摘要", ["web_scrape"]),
            WorkflowStepDefinition(4, "Analyze", "提取写作风格、故事逻辑和主线结构", "分析报告", ["llm_generate"]),
            WorkflowStepDefinition(5, "Suggest", "生成灵感报告和方向建议", "灵感报告", ["llm_generate"]),
            WorkflowStepDefinition(6, "Store", "将灵感报告入库到 worldbook", "worldbook 条目", ["upsert_entity"]),
        ],
    ),
    "wf-02": WorkflowDefinition(
        workflow_id="wf-02",
        name="世界观与角色构建",
        trigger="WF-01 完成后自动触发",
        description="基于灵感报告设计世界观、角色、剧情线和关系网络。",
        dependencies=["wf-01"],
        output="世界观实体、角色实体、剧情线实体、关系 -> Neo4j + SQLite",
        steps=[
            WorkflowStepDefinition(1, "Plan", "规划世界观设计方案", "设计计划", ["llm_generate"]),
            WorkflowStepDefinition(2, "Design World", "设计地点、规则、力量体系", "世界观条目", ["llm_generate", "upsert_entity"]),
            WorkflowStepDefinition(3, "Design Characters", "创建角色性格、动机和关系种子", "角色实体", ["llm_generate", "upsert_entity"]),
            WorkflowStepDefinition(4, "Design Plots", "设计主线和支线剧情", "剧情线实体", ["llm_generate", "upsert_entity"]),
            WorkflowStepDefinition(5, "Build Relationships", "构建角色关系网络", "关系记录", ["upsert_relationship"]),
        ],
    ),
    "wf-03": WorkflowDefinition(
        workflow_id="wf-03",
        name="章节大纲规划",
        trigger="WF-02 完成后自动触发",
        description="基于世界观、角色和剧情线规划章节总数、顺序和每章节拍。",
        dependencies=["wf-02"],
        output="ChapterPlan 记录列表",
        steps=[
            WorkflowStepDefinition(1, "Plan", "决定章节总数和叙事策略", "章节策略", ["llm_generate"]),
            WorkflowStepDefinition(2, "Outline Per Chapter", "为每章生成 design_brief 和 beat_sheet", "章节大纲", ["llm_generate"]),
            WorkflowStepDefinition(3, "Link Plots", "关联章节与剧情线并决定顺序", "章节剧情线关系", ["upsert_relationship"]),
            WorkflowStepDefinition(4, "Store Outlines", "将章节大纲存入数据库", "ChapterPlan 列表", ["query_sqlite"]),
        ],
    ),
    "wf-04": WorkflowDefinition(
        workflow_id="wf-04",
        name="章节写作执行",
        trigger="WF-03 完成后自动触发，或人类手动触发章节范围",
        description="AI 自主选择写作策略，生成初稿、一致性检查、修订、实体提取和 Markdown 导出。",
        dependencies=["wf-03"],
        output="章节正文 + 一致性报告 + 图数据库更新 + .md 文件",
        steps=[
            WorkflowStepDefinition(1, "Plan Writing Strategy", "决定顺序写、主干先写或混合策略", "写作策略", ["llm_generate"]),
            WorkflowStepDefinition(2, "Generate Draft", "生成章节初稿", "draft_content", ["llm_generate"]),
            WorkflowStepDefinition(3, "Consistency Check", "检查初稿与设定、已有章节的一致性", "consistency_report", ["check_consistency"]),
            WorkflowStepDefinition(4, "Revise", "根据报告修订为最终稿", "final_content", ["llm_generate"]),
            WorkflowStepDefinition(5, "Extract Entities", "从最终稿提取实体和关系", "图谱变更摘要", ["extract_entities"]),
            WorkflowStepDefinition(6, "Store to Neo4j", "写入实体和关系", "Neo4j/SQLite 更新", ["upsert_entity", "upsert_relationship"]),
            WorkflowStepDefinition(7, "Export MD", "导出章节 Markdown", ".md 文件", ["export_chapter_md"]),
        ],
    ),
    "wf-05": WorkflowDefinition(
        workflow_id="wf-05",
        name="实体关系提取与图入库",
        trigger="贯穿 WF-01 至 WF-04，每产生新内容即触发",
        description="AI 分析文本，去重合并后写入图数据库并记录 graph_mutation 日志。",
        dependencies=[],
        output="新增/更新实体与关系数量摘要",
        steps=[
            WorkflowStepDefinition(1, "Extract", "从文本提取实体和关系", "候选实体关系", ["extract_entities"]),
            WorkflowStepDefinition(2, "Deduplicate", "对比已有实体并决定新增或更新", "去重计划", ["query_graph", "query_sqlite"]),
            WorkflowStepDefinition(3, "Upsert", "写入实体和关系", "图谱变更", ["upsert_entity", "upsert_relationship"]),
            WorkflowStepDefinition(4, "Log", "记录 TaskLog graph_mutation", "审计日志", ["query_sqlite"]),
        ],
    ),
}


def list_workflow_definitions() -> list[WorkflowDefinition]:
    return list(WORKFLOW_REGISTRY.values())


def get_workflow_definition(workflow_id: str) -> WorkflowDefinition | None:
    return WORKFLOW_REGISTRY.get(workflow_id.lower())


def execute_registered_workflow(
    db: Session,
    project_id: int,
    workflow_id: str,
    payload: WorkflowExecuteRequest,
) -> dict:
    definition = get_workflow_definition(workflow_id)
    if definition is None:
        raise ValueError("Workflow not found")
    if payload.workflow_execution_id:
        existing_task = get_task_by_workflow_execution_id(db, project_id, payload.workflow_execution_id)
        if existing_task is not None:
            return {
                "definition": definition,
                "task": existing_task,
                "steps": list_task_steps(db, existing_task.id),
                "state": None,
                "idempotent_replay": True,
            }
    objective = payload.objective or f"Execute {definition.workflow_id}: {definition.name}"
    plan_text = "\n".join(
        f"{step.step_no}. {step.name}: {step.objective} -> {step.expected_output}" for step in definition.steps
    )
    task = create_task(
        db,
        project_id,
        AITaskCreate(
            task_type=definition.workflow_id,
            module_type="langgraph_workflow",
            title=definition.name,
            input_payload=objective,
            plan_text=plan_text,
            workflow_execution_id=payload.workflow_execution_id,
            status="running",
        ),
    )
    workflow_payload = {
        "workflow_id": definition.workflow_id,
        "name": definition.name,
        "dependencies": definition.dependencies,
        "output": definition.output,
        "steps": [
            {
                "step_no": step.step_no,
                "name": step.name,
                "objective": step.objective,
                "expected_output": step.expected_output,
                "tool_hints": step.tool_hints,
            }
            for step in definition.steps
        ],
    }
    state = run_plan_execute_workflow(
        db,
        project_id,
        task,
        objective,
        workflow_definition=workflow_payload,
        max_steps=max(1, min(payload.max_steps, 20)),
        hyperparameters=payload.hyperparameters,
    )
    log_paths = write_workflow_execution_log(db, task)
    return {
        "definition": definition,
        "task": task,
        "steps": list_task_steps(db, task.id),
        "state": state,
        "log_paths": log_paths,
        "idempotent_replay": False,
    }
