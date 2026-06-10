from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.models.ai_task import AITask, TaskLog
from app.schemas.task_runtime import TaskRuntimeState, TaskStepRuntimeState
from app.services import (
    ai_workflow_graph_service,
    entity_extraction_service,
    task_service,
    workflow_log_service,
    workflow_tool_service,
)


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
    states: dict[tuple[int, int], TaskRuntimeState] = {}

    def set_task_runtime_state(project_id, task_id, payload):
        state = TaskRuntimeState(
            project_id=project_id,
            task_id=task_id,
            status=payload.status,
            current_step=payload.current_step,
            message=payload.message,
        )
        states[(project_id, task_id)] = state
        return state

    def get_task_runtime_state(project_id, task_id):
        return states.get((project_id, task_id))

    def set_task_step_runtime_state(project_id, task_id, payload):
        return TaskStepRuntimeState(
            project_id=project_id,
            task_id=task_id,
            step_no=payload.step_no,
            step_name=payload.step_name,
            status=payload.status,
            react_state=payload.react_state,
            message=payload.message,
        )

    monkeypatch.setattr(task_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(task_service, "set_task_step_runtime_state", set_task_step_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "get_task_runtime_state", get_task_runtime_state)
    monkeypatch.setattr(ai_workflow_graph_service, "set_task_step_runtime_state", set_task_step_runtime_state)


def disable_neo4j_sync(monkeypatch) -> None:
    monkeypatch.setattr(entity_extraction_service, "sync_character_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_worldbook_entry_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_relationship_to_neo4j", lambda *_args, **_kwargs: False)


def test_workflow_registry_exposes_five_required_workflows() -> None:
    project_response = client.post("/api/v1/projects", json={"name": "Workflow 注册测试"})
    assert project_response.status_code == 201

    response = client.get("/api/v1/projects/1/workflows")

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["workflow_id"] for item in items] == ["wf-01", "wf-02", "wf-03", "wf-04", "wf-05"]
    wf04 = next(item for item in items if item["workflow_id"] == "wf-04")
    assert "wf-03" in wf04["dependencies"]
    assert [step["name"] for step in wf04["steps"]] == [
        "Plan Writing Strategy",
        "Generate Draft",
        "Consistency Check",
        "Revise",
        "Extract Entities",
        "Store to Neo4j",
        "Export MD",
    ]


def test_execute_registered_workflow_creates_traceable_task(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    disable_neo4j_sync(monkeypatch)
    log_root = Path("D:/Study/novel_ai_editer/.tmp/test_workflow_logs")
    monkeypatch.setattr(workflow_log_service, "WORKFLOW_LOG_ROOT", log_root)

    project_response = client.post("/api/v1/projects", json={"name": "Workflow 执行测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/workflows/wf-05/execute",
        json={"objective": "角色：林岚。地点：雾城。林岚 与 周启 同盟", "max_steps": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["workflow"]["workflow_id"] == "wf-05"
    assert data["task"]["task_type"] == "wf-05"
    assert data["task"]["module_type"] == "langgraph_workflow"
    assert data["task"]["tool_trace"]
    assert [step["step_type"] for step in data["steps"]] == [
        "planner",
        "executor",
        "replanner",
        "executor",
        "replanner",
        "executor",
        "replanner",
    ]
    assert data["steps"][1]["step_name"] == "Executor Agent - Extract"
    assert data["steps"][3]["step_name"] == "Executor Agent - Deduplicate"
    assert data["steps"][5]["step_name"] == "Executor Agent - Upsert"
    assert "Planner Agent" in data["task"]["reasoning_trace"]
    assert "Replanner Agent" in data["task"]["reasoning_trace"]

    tool_trace = data["task"]["tool_trace"]
    assert "extract_entities" in tool_trace
    assert "query_graph" in tool_trace
    assert "query_sqlite" in tool_trace
    assert "upsert_entity" in tool_trace
    assert "upsert_relationship" in tool_trace

    with TestingSessionLocal() as db:
        task_id = data["task"]["id"]
        planner_log = db.scalar(select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.log_type == "planner"))
    assert planner_log is not None
    assert "tool_node_registered" in planner_log.payload
    assert "extract_entities" in planner_log.payload

    plan_path = log_root / "wf-05_entity_extraction" / "plan.md"
    trace_path = log_root / "wf-05_entity_extraction" / "trace.md"
    assert plan_path.exists()
    assert trace_path.exists()
    assert "Extract" in plan_path.read_text(encoding="utf-8")
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "Planner Agent" in trace_text
    assert "Tool Trace" in trace_text


def test_execute_registered_workflow_is_idempotent_by_execution_id(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    disable_neo4j_sync(monkeypatch)

    project_response = client.post("/api/v1/projects", json={"name": "Workflow 幂等测试"})
    assert project_response.status_code == 201
    payload = {
        "objective": "角色：林岚。地点：雾城。",
        "max_steps": 2,
        "workflow_execution_id": "wf-05-demo-exec-001",
    }

    first_response = client.post("/api/v1/projects/1/workflows/wf-05/execute", json=payload)
    second_response = client.post("/api/v1/projects/1/workflows/wf-05/execute", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_data = first_response.json()["data"]
    second_data = second_response.json()["data"]
    assert first_data["idempotent_replay"] is False
    assert second_data["idempotent_replay"] is True
    assert second_data["task"]["id"] == first_data["task"]["id"]
    assert second_data["task"]["workflow_execution_id"] == "wf-05-demo-exec-001"

    with TestingSessionLocal() as db:
        task_count = db.scalar(
            select(func.count()).select_from(AITask).where(AITask.workflow_execution_id == "wf-05-demo-exec-001")
        )

    assert task_count == 1


def test_wf01_executes_search_and_scrape_tools_with_auditable_degraded_state(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: None)
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: None)

    project_response = client.post("/api/v1/projects", json={"name": "WF01 搜索抓取测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/workflows/wf-01/execute",
        json={"objective": "寻找都市异能悬疑小说趋势", "max_steps": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    tool_trace = data["task"]["tool_trace"]
    assert "web_search" in tool_trace
    assert "web_scrape" in tool_trace
    assert "missing_tavily_key" in tool_trace
    assert "missing_url" in tool_trace
    assert data["task"]["status"] == "completed"


def test_wf01_passes_search_results_into_scrape_tool(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)

    class FakeTavilyClient:
        def search(self, **_kwargs) -> dict:
            return {
                "results": [
                    {
                        "title": "都市异能趋势",
                        "url": "https://example.com/hot",
                        "content": "异能 悬疑 反转",
                        "score": 0.9,
                    }
                ]
            }

    class FakeFirecrawlClient:
        def scrape(self, url: str) -> dict:
            return {"data": {"title": "抓取页", "markdown": f"抓取自 {url} 的趋势正文"}}

    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: FakeTavilyClient())
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: FakeFirecrawlClient())

    project_response = client.post("/api/v1/projects", json={"name": "WF01 搜索抓取传递测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/workflows/wf-01/execute",
        json={"objective": "寻找都市异能悬疑小说趋势", "max_steps": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    tool_trace = data["task"]["tool_trace"]
    assert "web_search" in tool_trace
    assert "web_scrape" in tool_trace
    assert "https://example.com/hot" in tool_trace
    assert "抓取自 https://example.com/hot" in tool_trace


def test_workflow_hyperparameters_enable_live_llm_fallback_trace(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    from app.services import openrouter_service

    def fake_generate_with_openrouter_fallback(**kwargs):
        assert kwargs["preferred_keywords"] == ["qwen", "deepseek"]
        return {
            "model": {"id": "deepseek/deepseek-test:free"},
            "completion": {"choices": [{"message": {"content": "fallback workflow completion"}}]},
            "attempts": [
                {"model_id": "qwen/qwen-test:free", "status": "failed", "error": "timeout"},
                {"model_id": "deepseek/deepseek-test:free", "status": "success", "error": None},
            ],
            "fallback_used": True,
        }

    monkeypatch.setattr(openrouter_service, "generate_with_openrouter_fallback", fake_generate_with_openrouter_fallback)

    project_response = client.post("/api/v1/projects", json={"name": "Workflow LLM fallback 测试"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/workflows/wf-01/execute",
        json={
            "objective": "规划搜索策略",
            "max_steps": 1,
            "hyperparameters": {
                "live_llm": True,
                "model_preference": ["qwen", "deepseek"],
            },
        },
    )

    assert response.status_code == 200
    tool_trace = response.json()["data"]["task"]["tool_trace"]
    assert "llm_generate" in tool_trace
    assert "fallback_used" in tool_trace
    assert "qwen/qwen-test:free" in tool_trace
    assert "deepseek/deepseek-test:free" in tool_trace
