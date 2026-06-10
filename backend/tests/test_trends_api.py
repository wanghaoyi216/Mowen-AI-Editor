import json
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.db.base import Base
from app.main import create_application
from app.services import trend_service


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


def test_execute_trend_returns_readable_configuration_error(monkeypatch) -> None:
    monkeypatch.setattr(trend_service, "build_tavily_client", lambda: None)

    project_response = client.post("/api/v1/projects", json={"name": "配置测试项目"})
    assert project_response.status_code == 201

    response = client.post(
        "/api/v1/projects/1/trend-explorations/execute",
        json={"title": "热点测试", "query_text": "网络小说趋势"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Tavily key is not configured"


class FakeTavilyClient:
    def search(self, **kwargs) -> dict:
        return {
            "query": kwargs["query"],
            "results": [
                {
                    "title": "短剧式强反转悬疑升温",
                    "content": "短剧 反转 悬疑 情绪钩子 推动 网络小说题材变化",
                    "url": "https://example.com/a",
                    "score": 0.91,
                },
                {
                    "title": "群像奇幻与规则怪谈融合",
                    "content": "群像 奇幻 规则怪谈 世界观 角色关系",
                    "url": "https://example.com/b",
                    "score": 0.82,
                },
            ],
        }


def test_execute_trend_builds_structured_insights_and_mapping_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(trend_service, "build_tavily_client", lambda: FakeTavilyClient())
    monkeypatch.setattr(trend_service, "build_firecrawl_client", lambda: None)

    project_response = client.post("/api/v1/projects", json={"name": "趋势测试项目"})
    assert project_response.status_code == 201

    trend_response = client.post(
        "/api/v1/projects/1/trend-explorations/execute",
        json={"title": "热点测试", "query_text": "网络小说趋势 反转 悬疑"},
    )
    assert trend_response.status_code == 200
    trend = trend_response.json()["data"]
    assert trend["status"] == "completed"

    topics = json.loads(trend["extracted_topics"])
    tags = json.loads(trend["extracted_tags"])
    directions = json.loads(trend["suggested_directions"])
    raw_findings = json.loads(trend["raw_findings"])

    assert topics[0]["title"] == "短剧式强反转悬疑升温"
    assert "悬疑" in tags
    assert directions[0]["source_url"] == "https://example.com/a"
    assert raw_findings["sources"][0]["url"] == "https://example.com/a"

    first_map_response = client.post(
        "/api/v1/projects/1/trend-explorations/map-assets",
        json={"trend_id": trend["id"]},
    )
    second_map_response = client.post(
        "/api/v1/projects/1/trend-explorations/map-assets",
        json={"trend_id": trend["id"]},
    )

    assert first_map_response.status_code == 200
    assert second_map_response.status_code == 200
    first_data = first_map_response.json()["data"]
    second_data = second_map_response.json()["data"]
    assert [item["id"] for item in second_data["plot_lines"]] == [item["id"] for item in first_data["plot_lines"]]
    assert [item["id"] for item in second_data["characters"]] == [item["id"] for item in first_data["characters"]]
    assert [item["id"] for item in second_data["worldbook_entries"]] == [
        item["id"] for item in first_data["worldbook_entries"]
    ]
