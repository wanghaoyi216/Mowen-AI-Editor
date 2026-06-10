from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.duckduckgo_client import build_duckduckgo_client
from app.integrations.firecrawl_client import build_firecrawl_client
from app.integrations.tavily_client import build_tavily_client

logger = logging.getLogger(__name__)


def web_search_tool(_db: Session, _project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """三路搜索引擎轮询：Tavily → Firecrawl.search → DuckDuckGo → 离线。

    任何一路失败都自动降级，绝不死磕单点（避免用户卡在 504/401 上）。
    """
    query = str(payload.get("query") or payload.get("objective") or "").strip()
    if not query:
        return {"mode": "skipped", "status": "missing_query", "results": []}

    search_depth = str(payload.get("search_depth") or "advanced")
    max_results = int(payload.get("max_results") or 5)

    tavily_client = build_tavily_client()
    firecrawl_client = build_firecrawl_client()
    duckduckgo_client = build_duckduckgo_client()

    fallback_chain: list[str] = []
    source: str = "none"
    results: list[dict] = []

    # 1) Tavily
    if tavily_client is not None:
        try:
            response = tavily_client.search(query=query, search_depth=search_depth, max_results=max_results)
            raw = response.get("results", []) if isinstance(response, dict) else []
            if isinstance(raw, list) and raw:
                results = _compact_tavily(raw, max_results)
                source = "tavily"
                fallback_chain.append("tavily")
                logger.info("web_search_tool: Tavily OK (%s results)", len(results))
        except Exception as exc:
            logger.error("web_search_tool Tavily failed: %s", exc, exc_info=True)
            fallback_chain.append(f"tavily:error:{type(exc).__name__}")
    else:
        fallback_chain.append("tavily:no_key")

    # 2) Firecrawl search
    if not results and firecrawl_client is not None:
        try:
            fc_resp = firecrawl_client.search(query=query, limit=max_results, lang="zh", country="CN")
            fc_data = fc_resp.get("data") if isinstance(fc_resp, dict) else None
            if not isinstance(fc_data, list):
                fc_data = fc_resp.get("web") or fc_resp.get("results") or []
            if isinstance(fc_data, list) and fc_data:
                results = _compact_firecrawl(fc_data, max_results)
                source = "firecrawl"
                fallback_chain.append("firecrawl")
                logger.info("web_search_tool: Firecrawl OK (%s results)", len(results))
            else:
                fallback_chain.append("firecrawl:empty")
        except Exception as exc:
            logger.error("web_search_tool Firecrawl failed: %s", exc, exc_info=True)
            fallback_chain.append(f"firecrawl:error:{type(exc).__name__}")
    elif not results:
        fallback_chain.append("firecrawl:no_key")

    # 3) DuckDuckGo 公开搜索
    if not results:
        try:
            ddg_resp = duckduckgo_client.search(query=query, max_results=max_results)
            ddg_raw = ddg_resp.get("results", []) if isinstance(ddg_resp, dict) else []
            if isinstance(ddg_raw, list) and ddg_raw:
                results = _compact_ddg(ddg_raw, max_results)
                source = "duckduckgo"
                fallback_chain.append("duckduckgo")
                logger.info("web_search_tool: DuckDuckGo OK (%s results)", len(results))
            else:
                fallback_chain.append("duckduckgo:empty")
        except Exception as exc:
            logger.error("web_search_tool DuckDuckGo failed: %s", exc, exc_info=True)
            fallback_chain.append(f"duckduckgo:error:{type(exc).__name__}")

    if results:
        return {
            "mode": "live",
            "status": "success",
            "query": query,
            "search_depth": search_depth,
            "source": source,
            "fallback_chain": fallback_chain,
            "results": results,
            "raw_result_count": len(results),
        }

    return {
        "mode": "configuration_required",
        "status": "skipped",
        "error_code": "ALL_SEARCH_SOURCES_FAILED",
        "remediation": "三路搜索引擎（Tavily / Firecrawl / DuckDuckGo）全部失败，请检查网络与 API key",
        "fallback_chain": fallback_chain,
        "query": query,
        "results": [],
    }


def _compact_tavily(items: list[Any], max_results: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:max_results]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score"),
            }
        )
    return compact


def _compact_firecrawl(items: list[Any], max_results: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:max_results]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("name") or "").strip()
        url = (item.get("url") or item.get("link") or "").strip()
        content = (
            item.get("description")
            or item.get("snippet")
            or item.get("markdown")
            or item.get("content")
            or ""
        ).strip()
        if not url:
            continue
        compact.append({"title": title[:200], "url": url, "content": content[:600], "score": item.get("score") or 0.5})
    return compact


def _compact_ddg(items: list[Any], max_results: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:max_results]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or "").strip()
        if not url:
            continue
        compact.append({"title": title[:200] or url, "url": url, "content": content[:600], "score": item.get("score") or 0.5})
    return compact


def web_scrape_tool(_db: Session, _project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    if not url:
        search_results = payload.get("search_results") or payload.get("results") or []
        if isinstance(search_results, list):
            for item in search_results:
                if isinstance(item, dict) and item.get("url"):
                    url = str(item["url"]).strip()
                    break
    if not url:
        return {"mode": "skipped", "status": "missing_url", "summary": "No URL supplied for web_scrape."}

    client = build_firecrawl_client()
    if client is None:
        return {
            "mode": "configuration_required",
            "status": "skipped",
            "error_code": "MISSING_FIRECRAWL_KEY",
            "remediation": "请在 backend/.env 设置 FIRECRAWL_API_KEY 后重启后端",
            "url": url,
        }

    scrape = client.scrape(url)
    data = scrape.get("data") if isinstance(scrape, dict) else None
    if not isinstance(data, dict):
        data = scrape if isinstance(scrape, dict) else {"content": str(scrape)}
    metadata = data.get("metadata")
    title = data.get("title")
    if title is None and isinstance(metadata, dict):
        title = metadata.get("title")
    markdown = data.get("markdown") or data.get("content") or data.get("text") or ""
    return {
        "mode": "live",
        "status": "success",
        "url": url,
        "title": title,
        "content_preview": str(markdown)[:1200],
        "raw": scrape,
    }
