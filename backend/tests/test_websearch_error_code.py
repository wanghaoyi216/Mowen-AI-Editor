import pytest

from app.services import workflow_tool_service


def test_web_search_tool_returns_misssing_tavily_key_error_code(monkeypatch) -> None:
    """当 TAVILY_API_KEY 未配置时，web_search_tool 必须返回结构化 error_code。"""
    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: None)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_KEY", raising=False)

    result = workflow_tool_service.web_search_tool(None, 1, {"query": "test"})

    assert result["mode"] == "configuration_required"
    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_TAVILY_KEY"
    assert isinstance(result.get("remediation"), str)
    assert result["remediation"], "remediation 必须是非空字符串"
    assert "TAVILY_API_KEY" in result["remediation"]
    assert result["query"] == "test"
    assert result["results"] == []


def test_web_scrape_tool_returns_missing_firecrawl_key_error_code(monkeypatch) -> None:
    """当 FIRECRAWL_API_KEY 未配置时，web_scrape_tool 必须返回结构化 error_code。"""
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: None)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_KEY", raising=False)

    result = workflow_tool_service.web_scrape_tool(
        None,
        1,
        {"url": "https://example.com/article"},
    )

    assert result["mode"] == "configuration_required"
    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_FIRECRAWL_KEY"
    assert isinstance(result.get("remediation"), str)
    assert result["remediation"], "remediation 必须是非空字符串"
    assert "FIRECRAWL_API_KEY" in result["remediation"]
    assert result["url"] == "https://example.com/article"


def test_web_search_tool_error_response_with_objective_payload(monkeypatch) -> None:
    """使用 objective 字段作为 query 触发时，同样要返回结构化 error_code。"""
    monkeypatch.setattr(workflow_tool_service, "build_tavily_client", lambda: None)

    result = workflow_tool_service.web_search_tool(None, 1, {"objective": "objective 关键词"})

    assert result["error_code"] == "MISSING_TAVILY_KEY"
    assert result["query"] == "objective 关键词"
    assert result["results"] == []


def test_web_scrape_tool_error_response_when_picking_url_from_search_results(monkeypatch) -> None:
    """当 url 从 search_results 推断且 FIRECRAWL key 缺失时，仍要返回结构化 error_code。"""
    monkeypatch.setattr(workflow_tool_service, "build_firecrawl_client", lambda: None)

    result = workflow_tool_service.web_scrape_tool(
        None,
        1,
        {"search_results": [{"url": "https://example.com/picked"}]},
    )

    assert result["error_code"] == "MISSING_FIRECRAWL_KEY"
    assert result["url"] == "https://example.com/picked"
    assert "remediation" in result
