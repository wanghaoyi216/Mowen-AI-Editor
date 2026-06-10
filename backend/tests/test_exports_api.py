import zipfile
from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.services import export_service


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


def test_export_project_files_and_archive(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(export_service, "EXPORT_ROOT", tmp_path / "exports")

    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "导出测试项目",
            "theme": "都市异能",
            "writing_style": "悬疑爽文",
        },
    )
    assert project_response.status_code == 201

    character_response = client.post("/api/v1/projects/1/characters", json={"name": "林岚", "role_type": "主角"})
    plot_response = client.post("/api/v1/projects/1/plot-lines", json={"title": "主线A", "plot_type": "main"})
    worldbook_response = client.post(
        "/api/v1/projects/1/worldbook",
        json={"title": "雾城", "category": "location", "content": "城市常年被雾气覆盖。"},
    )
    chapter_response = client.post(
        "/api/v1/projects/1/chapters",
        json={
            "chapter_no": 1,
            "title": "雾中来信",
            "summary": "主角收到匿名信。",
            "final_content": "林岚在雾中发现第一封信。",
            "word_count": 13,
            "status": "completed",
        },
    )

    assert character_response.status_code == 200
    assert plot_response.status_code == 200
    assert worldbook_response.status_code == 200
    assert chapter_response.status_code == 200

    files_response = client.post("/api/v1/projects/1/exports/files")
    assert files_response.status_code == 200
    data = files_response.json()["data"]
    export_dir = Path(data["export_dir"])

    chapter_file = export_dir / "chapters" / "第01章_雾中来信.md"
    assert chapter_file.exists()
    chapter_text = chapter_file.read_text(encoding="utf-8")
    assert "chapter_no: 1" in chapter_text
    assert 'title: "雾中来信"' in chapter_text
    assert "characters:" in chapter_text
    assert "林岚在雾中发现第一封信。" in chapter_text

    assert (export_dir / "导出测试项目_全本.md").exists()
    assert (export_dir / "assets" / "characters.json").exists()
    assert (export_dir / "assets" / "relationships.json").exists()
    assert (export_dir / "assets" / "plot_lines.json").exists()
    assert (export_dir / "assets" / "worldbook.json").exists()
    assert (export_dir / "assets" / "graph_export.json").exists()
    assert (export_dir / "assets" / "graph_export.png").read_bytes().startswith(b"\x89PNG")
    assert (export_dir / "workflow_logs" / "wf-04_chapter_writing" / "plan.md").exists()

    archive_response = client.post("/api/v1/projects/1/exports/archive")
    assert archive_response.status_code == 200
    archive_path = Path(archive_response.json()["data"]["archive_path"])
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert "导出测试项目/chapters/第01章_雾中来信.md" in names
    assert "导出测试项目/assets/worldbook.json" in names
