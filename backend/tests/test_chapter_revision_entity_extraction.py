from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.models.ai_task import TaskLog
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.character import Character
from app.models.character_relationship import CharacterRelationship
from app.services import chapter_ai_service, chapter_task_service, entity_extraction_service, task_service
from app.schemas.task_runtime import TaskRuntimeState, TaskStepRuntimeState


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
    def set_task_runtime_state(project_id, task_id, payload):
        return TaskRuntimeState(
            project_id=project_id,
            task_id=task_id,
            status=payload.status,
            current_step=payload.current_step,
            message=payload.message,
        )

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
    monkeypatch.setattr(chapter_task_service, "set_task_runtime_state", set_task_runtime_state)
    monkeypatch.setattr(chapter_task_service, "set_task_step_runtime_state", set_task_step_runtime_state)


def disable_external_sync(monkeypatch) -> None:
    monkeypatch.setattr(chapter_ai_service, "sync_chapter_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_character_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_worldbook_entry_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_relationship_to_neo4j", lambda *_args, **_kwargs: False)


def fake_openrouter(system_prompt: str, user_prompt: str, preferred_keywords=None, **kwargs):
    _ = system_prompt, user_prompt, preferred_keywords, kwargs
    return {
        "model": {"id": "test-model"},
        "completion": {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"characters":[{"name":"林岚","identity":"调查员"},{"name":"周启","identity":"档案员"}],'
                            '"relationships":[{"source":"林岚","target":"周启","relation_type":"同盟","intensity":3}],'
                            '"worldbook_entries":[{"title":"雾城","category":"location","content":"常年被雾覆盖。"}]}'
                        )
                    }
                }
            ]
        },
    }


def test_revision_task_sets_final_content_and_extracts_entities(monkeypatch) -> None:
    install_memory_runtime(monkeypatch)
    disable_external_sync(monkeypatch)
    monkeypatch.setattr(chapter_ai_service, "generate_with_openrouter", fake_openrouter)

    project_response = client.post("/api/v1/projects", json={"name": "章节实体提取测试"})
    assert project_response.status_code == 201

    with TestingSessionLocal() as db:
        chapter = Chapter(
            project_id=1,
            chapter_no=1,
            title="雾中来信",
            summary="匿名信出现",
            draft_content="旧稿",
            word_count=2,
            status="drafted",
            version=1,
        )
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
        plan = ChapterPlan(
            project_id=1,
            chapter_id=chapter.id,
            title=chapter.title,
            design_brief="角色：林岚。地点：雾城。",
            beat_sheet="林岚与周启建立同盟。",
            asset_summary="角色：林岚\n角色：周启\n地点：雾城",
            status="designed",
        )
        db.add(plan)
        db.commit()
        chapter_id = chapter.id

    response = client.post(
        f"/api/v1/projects/1/chapters/{chapter_id}/revise-task",
        json={"revision_focus": "修复一致性", "style_hint": "悬疑", "word_target": 800},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["chapter"]["status"] == "completed"
    assert data["chapter"]["final_content"]
    assert data["version"]["operation_type"] == "revision"
    assert data["entity_extraction"]["added_entities"] == 3
    assert data["entity_extraction"]["added_relationships"] == 1

    with TestingSessionLocal() as db:
        characters = list(db.scalars(select(Character).where(Character.project_id == 1)))
        relationships = list(db.scalars(select(CharacterRelationship).where(CharacterRelationship.project_id == 1)))
        logs = list(db.scalars(select(TaskLog).where(TaskLog.log_type == "graph_mutation")))

    assert sorted(item.name for item in characters) == ["周启", "林岚"]
    assert len(relationships) == 1
    assert len(logs) == 1
