import json
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.models.ai_task import AITask, TaskLog
from app.models.character_relationship import CharacterRelationship
from app.models.worldbook_entry import WorldbookEntry
from app.services import entity_extraction_service


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


def disable_neo4j_sync(monkeypatch) -> None:
    monkeypatch.setattr(entity_extraction_service, "sync_character_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_worldbook_entry_to_neo4j", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(entity_extraction_service, "sync_relationship_to_neo4j", lambda *_args, **_kwargs: False)


def test_extract_entities_analyzes_before_store_and_logs_graph_mutation(monkeypatch) -> None:
    disable_neo4j_sync(monkeypatch)

    project_response = client.post("/api/v1/projects", json={"name": "实体提取测试"})
    assert project_response.status_code == 201
    with TestingSessionLocal() as db:
        task = AITask(
            project_id=1,
            task_type="wf-05",
            module_type="entity_extraction",
            title="实体入库测试",
            status="running",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    extraction_payload = {
        "text": json.dumps(
            {
                "characters": [
                    {"name": "林岚", "identity": "调查员"},
                    {"name": "周启", "identity": "档案员"},
                ],
                "worldbook_entries": [
                    {"title": "雾城", "category": "location", "content": "常年被雾覆盖的城市。"}
                ],
                "relationships": [
                    {"source": "林岚", "target": "周启", "relation_type": "同盟", "intensity": 4, "note": "共同调查"}
                ],
            },
            ensure_ascii=False,
        ),
        "source_type": "chapter",
        "source_ref": "chapter-1",
        "task_id": task_id,
    }

    first_response = client.post("/api/v1/projects/1/entity-extraction/extract", json=extraction_payload)
    second_response = client.post("/api/v1/projects/1/entity-extraction/extract", json=extraction_payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_data = first_response.json()["data"]
    second_data = second_response.json()["data"]
    assert first_data["added_entities"] == 3
    assert first_data["added_relationships"] == 1
    assert second_data["added_entities"] == 0
    assert second_data["added_relationships"] == 0

    with TestingSessionLocal() as db:
        worldbook = db.scalar(select(WorldbookEntry).where(WorldbookEntry.title == "雾城"))
        relationship = db.scalar(select(CharacterRelationship).where(CharacterRelationship.relation_type == "同盟"))
        logs = list(db.scalars(select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.log_type == "graph_mutation")))

    assert worldbook is not None
    assert worldbook.source_type == "chapter"
    assert relationship is not None
    assert relationship.intensity == 4
    assert len(logs) == 2
