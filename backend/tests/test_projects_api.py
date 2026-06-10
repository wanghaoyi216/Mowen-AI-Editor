from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application


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


def test_create_list_read_and_update_project() -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "星港遗梦",
            "genre": "科幻",
            "theme": "记忆与身份",
            "target_audience": "青年读者",
            "summary": "失忆领航员追查星港事故真相。",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["id"] == 1
    assert created["name"] == "星港遗梦"
    assert created["status"] == "draft"

    list_response = client.get("/api/v1/projects")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["data"]] == ["星港遗梦"]

    read_response = client.get("/api/v1/projects/1")
    assert read_response.status_code == 200
    assert read_response.json()["data"]["theme"] == "记忆与身份"

    update_response = client.patch(
        "/api/v1/projects/1",
        json={"status": "active", "tone": "冷峻"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["status"] == "active"
    assert updated["tone"] == "冷峻"


def test_create_project_persists_writing_constraints() -> None:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "字数约束项目",
            "genre": "玄幻",
            "writing_style": "网文爽文",
            "tone": "热血",
            "target_audience": "男性向",
            "min_words_per_chapter": 3000,
            "max_words_per_chapter": 5000,
            "target_chapters": 60,
        },
    )
    assert response.status_code == 201
    created = response.json()["data"]
    assert created["writing_style"] == "网文爽文"
    assert created["tone"] == "热血"
    assert created["target_audience"] == "男性向"
    assert created["min_words_per_chapter"] == 3000
    assert created["max_words_per_chapter"] == 5000
    assert created["target_chapters"] == 60

    read = client.get(f"/api/v1/projects/{created['id']}")
    assert read.status_code == 200
    data = read.json()["data"]
    assert data["min_words_per_chapter"] == 3000
    assert data["max_words_per_chapter"] == 5000


def test_create_project_rejects_empty_name() -> None:
    response = client.post("/api/v1/projects", json={"name": ""})

    assert response.status_code == 422


def test_read_missing_project_returns_404() -> None:
    response = client.get("/api/v1/projects/999")

    assert response.status_code == 404
