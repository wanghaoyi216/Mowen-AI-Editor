from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.schemas.task_runtime import TaskRuntimeState, TaskStepRuntimeState
from app.services import task_runtime_service, task_service


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


def install_memory_runtime(monkeypatch) -> tuple[
    dict[tuple[int, int], TaskRuntimeState],
    dict[tuple[int, int, int], TaskStepRuntimeState],
]:
    states: dict[tuple[int, int], TaskRuntimeState] = {}
    step_states: dict[tuple[int, int, int], TaskStepRuntimeState] = {}

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

    def get_task_step_runtime_states(project_id, task_id):
        return [
            state
            for (stored_project_id, stored_task_id, _step_no), state in step_states.items()
            if stored_project_id == project_id and stored_task_id == task_id
        ]

    monkeypatch.setattr(task_runtime_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(task_runtime_service, "get_task_runtime_state", get_task_runtime_state)
    monkeypatch.setattr(task_runtime_service, "set_task_step_runtime_state", set_task_step_runtime_state)
    monkeypatch.setattr(task_runtime_service, "get_task_step_runtime_states", get_task_step_runtime_states)
    monkeypatch.setattr(task_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(task_service, "set_task_step_runtime_state", set_task_step_runtime_state)
    return states, step_states


def test_task_control_pause_resume_stop_updates_runtime_and_task(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)

    project_response = client.post("/api/v1/projects", json={"name": "控制测试"})
    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={
            "task_type": "wf-04",
            "module_type": "langgraph_workflow",
            "title": "章节写作",
            "status": "running",
        },
    )
    assert project_response.status_code == 201
    assert task_response.status_code == 200
    task_id = task_response.json()["data"]["id"]

    pause_response = client.post(f"/api/v1/projects/1/tasks/{task_id}/control", json={"action": "pause"})
    resume_response = client.post(f"/api/v1/projects/1/tasks/{task_id}/control", json={"action": "resume"})
    stop_response = client.post(f"/api/v1/projects/1/tasks/{task_id}/control", json={"action": "stop"})
    task_read_response = client.get(f"/api/v1/projects/1/tasks/{task_id}")

    assert pause_response.status_code == 200
    assert pause_response.json()["data"]["status"] == "paused"
    assert resume_response.status_code == 200
    assert resume_response.json()["data"]["status"] == "running"
    assert stop_response.status_code == 200
    assert stop_response.json()["data"]["status"] == "stopped"
    assert task_read_response.json()["data"]["status"] == "stopped"


def test_task_control_rejects_unknown_action(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    client.post("/api/v1/projects", json={"name": "控制异常测试"})
    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={"task_type": "wf-01", "module_type": "langgraph_workflow", "title": "热点", "status": "running"},
    )
    task_id = task_response.json()["data"]["id"]

    response = client.post(f"/api/v1/projects/1/tasks/{task_id}/control", json={"action": "restart"})

    assert response.status_code == 400


def test_runtime_read_rebuilds_missing_task_state_from_database(monkeypatch) -> None:
    states, _step_states = install_memory_runtime(monkeypatch)
    client.post("/api/v1/projects", json={"name": "运行态恢复测试"})
    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={"task_type": "wf-01", "module_type": "langgraph_workflow", "title": "热点", "status": "running"},
    )
    task_id = task_response.json()["data"]["id"]
    step_response = client.post(
        f"/api/v1/projects/1/tasks/{task_id}/steps",
        json={
            "step_no": 1,
            "step_name": "Planner Agent",
            "step_type": "planner",
            "react_state": "plan",
            "status": "completed",
        },
    )
    assert step_response.status_code == 200
    states.clear()

    response = client.get(f"/api/v1/projects/1/tasks/{task_id}/runtime")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "running"
    assert data["current_step"] == "Planner Agent"
    assert "rebuilt from database" in data["message"]
    assert states[(1, task_id)].current_step == "Planner Agent"


def test_step_runtime_read_rebuilds_missing_step_states_from_database(monkeypatch) -> None:
    _states, step_states = install_memory_runtime(monkeypatch)
    client.post("/api/v1/projects", json={"name": "步骤运行态恢复测试"})
    task_response = client.post(
        "/api/v1/projects/1/tasks",
        json={"task_type": "wf-04", "module_type": "langgraph_workflow", "title": "章节写作", "status": "running"},
    )
    task_id = task_response.json()["data"]["id"]
    client.post(
        f"/api/v1/projects/1/tasks/{task_id}/steps",
        json={
            "step_no": 1,
            "step_name": "Generate Draft",
            "step_type": "executor",
            "react_state": "action",
            "status": "completed",
        },
    )
    client.post(
        f"/api/v1/projects/1/tasks/{task_id}/steps",
        json={
            "step_no": 2,
            "step_name": "Revise",
            "step_type": "executor",
            "react_state": "action",
            "status": "running",
        },
    )
    step_states.clear()

    response = client.get(f"/api/v1/projects/1/tasks/{task_id}/step-runtime")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["step_name"] for item in data] == ["Generate Draft", "Revise"]
    assert data[0]["status"] == "completed"
    assert data[1]["status"] == "running"
    assert "rebuilt from database" in data[0]["message"]
