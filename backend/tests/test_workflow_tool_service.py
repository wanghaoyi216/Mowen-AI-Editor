from app.services import workflow_tool_service


class FakeTavilyClient:
    def search(self, **kwargs) -> dict:
        return {
            "query": kwargs["query"],
            "results": [
                {
                    "title": "爆款趋势观察",
                    "url": "https://example.com/trend",
                    "content": "悬疑 反转 情绪钩子",
                    "score": 0.93,
                }
            ],
        }


class FakeFirecrawlClient:
    def scrape(self, url: str) -> dict:
        return {
            "data": {
                "title": "趋势页面",
                "markdown": f"# 页面\n来自 {url} 的正文",
                "metadata": {"title": "备用标题"},
            }
        }


def test_web_search_reports_configuration_when_tavily_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: None)

    result = workflow_tool_service.web_search_tool(None, 1, {"query": "网络小说趋势"})

    assert result["mode"] == "configuration_required"
    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_TAVILY_KEY"
    assert result["remediation"]
    assert result["results"] == []


def test_web_search_uses_tavily_client(monkeypatch) -> None:
    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: FakeTavilyClient())

    result = workflow_tool_service.web_search_tool(None, 1, {"query": "悬疑 反转", "max_results": 1})

    assert result["mode"] == "live"
    assert result["status"] == "success"
    assert result["results"][0]["title"] == "爆款趋势观察"
    assert result["results"][0]["url"] == "https://example.com/trend"


def test_web_scrape_reports_configuration_when_firecrawl_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: None)

    result = workflow_tool_service.web_scrape_tool(None, 1, {"url": "https://example.com/trend"})

    assert result["mode"] == "configuration_required"
    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_FIRECRAWL_KEY"
    assert result["remediation"]
    assert result["url"] == "https://example.com/trend"


def test_web_scrape_uses_firecrawl_client_and_can_pick_url_from_search_results(monkeypatch) -> None:
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: FakeFirecrawlClient())

    result = workflow_tool_service.web_scrape_tool(
        None,
        1,
        {"search_results": [{"url": "https://example.com/trend"}]},
    )

    assert result["mode"] == "live"
    assert result["status"] == "success"
    assert result["title"] == "趋势页面"
    assert "正文" in result["content_preview"]
