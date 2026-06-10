"""DuckDuckGo 公开搜索（无需 API key 的兜底引擎）。

两个端点：
  * https://api.duckduckgo.com/  —— 官方 instant answer API，返回 JSON
  * https://duckduckgo.com/html/   —— HTML lite 端点，需要简单解析

零成本、零密钥、但返回质量差于 Tavily/Firecrawl，所以放在第 3 位。
"""

from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import unquote

import httpx

from app.core.config import settings
from app.core.resilience import with_retries

logger = logging.getLogger(__name__)


class DuckDuckGoClient:
    """DuckDuckGo 公开搜索：先试 instant-answer API，再试 html lite 端点。"""

    INSTANT_ANSWER_URL = "https://api.duckduckgo.com/"
    HTML_LITE_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout or float(settings.external_request_timeout_seconds)

    def search(self, query: str, max_results: int = 5) -> dict:
        """返回结构仿 Tavily/Firecrawl.search：{"results": [{"title","url","content","score"}], "source": "duckduckgo"}"""

        def operation_instant() -> dict:
            response = httpx.get(
                self.INSTANT_ANSWER_URL,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=self._timeout,
                headers={"User-Agent": "NovelAIEdtor/1.0"},
            )
            response.raise_for_status()
            return response.json()

        try:
            data = with_retries(
                operation_instant,
                retries=max(1, settings.external_request_retries // 2 or 1),
                retry_exceptions=(httpx.HTTPError,),
            )
            results = _parse_instant_answer(data, max_results)
            if results:
                return {"source": "duckduckgo", "results": results, "query": query}
        except Exception as exc:
            logger.warning("DuckDuckGo instant-answer failed: %s", exc)

        # 退到 html lite
        def operation_html() -> str:
            response = httpx.post(
                self.HTML_LITE_URL,
                data={"q": query, "kl": "cn-zh"},
                timeout=self._timeout,
                headers={"User-Agent": "NovelAIEdtor/1.0"},
            )
            response.raise_for_status()
            return response.text

        try:
            html_text = with_retries(
                operation_html,
                retries=max(1, settings.external_request_retries // 2 or 1),
                retry_exceptions=(httpx.HTTPError,),
            )
            results = _parse_html_lite(html_text, max_results)
            return {"source": "duckduckgo", "results": results, "query": query}
        except Exception as exc:
            logger.warning("DuckDuckGo html-lite failed: %s", exc)
            return {"source": "duckduckgo", "results": [], "query": query, "error": str(exc)}


def _parse_instant_answer(data: dict, max_results: int) -> list[dict]:
    """解析 instant-answer API 返回。"""
    results: list[dict] = []
    abstract_text = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    if abstract_text and abstract_url:
        results.append(
            {
                "title": (data.get("Heading") or "DuckDuckGo Abstract").strip(),
                "url": abstract_url,
                "content": abstract_text,
                "score": 0.95,
            }
        )
    for topic in (data.get("RelatedTopics") or [])[: max_results - len(results)]:
        if not isinstance(topic, dict):
            continue
        text = (topic.get("Text") or "").strip()
        first_url = (topic.get("FirstURL") or "").strip()
        if text and first_url:
            results.append(
                {
                    "title": text.split(" - ")[0][:120] if " - " in text else text[:120],
                    "url": first_url,
                    "content": text,
                    "score": 0.6,
                }
            )
        # 嵌套 Topics（category 内）
        for sub in (topic.get("Topics") or [])[: max_results - len(results)]:
            if not isinstance(sub, dict):
                continue
            sub_text = (sub.get("Text") or "").strip()
            sub_url = (sub.get("FirstURL") or "").strip()
            if sub_text and sub_url:
                results.append(
                    {
                        "title": sub_text.split(" - ")[0][:120],
                        "url": sub_url,
                        "content": sub_text,
                        "score": 0.5,
                    }
                )
        if len(results) >= max_results:
            break
    return results[:max_results]


_LINK_HTML_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_HTML_RE = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: str) -> str:
    return unescape(_TAG_RE.sub("", value)).strip()


def _parse_html_lite(html: str, max_results: int) -> list[dict]:
    """解析 html.duckduckgo.com 的 lite HTML。"""
    results: list[dict] = []
    links = _LINK_HTML_RE.findall(html)
    snippets = _SNIPPET_HTML_RE.findall(html)
    for idx, (raw_url, title_html) in enumerate(links[:max_results]):
        url = unquote(raw_url)
        if url.startswith("//"):
            url = "https:" + url
        title = _strip_html(title_html)
        content = _strip_html(snippets[idx]) if idx < len(snippets) else ""
        if not title:
            continue
        results.append({"title": title[:120], "url": url, "content": content, "score": max(0.2, 0.7 - idx * 0.1)})
    return results


def build_duckduckgo_client() -> DuckDuckGoClient:
    """DuckDuckGo 公开搜索无需 key，直接返回 client。"""
    return DuckDuckGoClient()
