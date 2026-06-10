import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.duckduckgo_client import build_duckduckgo_client
from app.integrations.firecrawl_client import build_firecrawl_client
from app.integrations.tavily_client import build_tavily_client
from app.models.trend_exploration import TrendExploration
from app.schemas.trend_exploration import TrendExplorationCreate
from app.schemas.task_runtime import TaskStatusUpdate
from app.services.task_runtime_service import set_task_runtime_state

MAX_TEXT_LENGTH = 280
logger = logging.getLogger(__name__)

FALLBACK_TREND_KEYWORDS = [
    "赛博修仙",
    "规则怪谈",
    "末日重建",
    "群像权谋",
    "都市异能",
    "无限流副本",
    "AI共生",
    "东方玄幻",
    "悬疑反转",
    "情绪爽点",
]


def _fallback_search_response(query_text: str, max_results: int) -> dict:
    results = []
    for index, keyword in enumerate(FALLBACK_TREND_KEYWORDS[:max_results], start=1):
        results.append(
            {
                "title": f"{keyword}题材趋势",
                "content": (
                    f"{keyword}适合与「{query_text}」结合，突出清晰目标、强冲突、"
                    "持续升级和可视化卖点，可作为离线降级题材方向。"
                ),
                "url": "",
                "score": max(0.1, 1 - index * 0.06),
            }
        )
    return {
        "query": query_text,
        "fallback": True,
        "results": results,
    }


def _compact_text(value: object, limit: int = MAX_TEXT_LENGTH) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _dedupe(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip(" ，,。.;；：:|/-")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _extract_tags(query_text: str, search_results: list[dict]) -> list[str]:
    keyword_candidates: list[str] = []
    corpus = " ".join(
        [query_text]
        + [
            f"{item.get('title') or ''} {item.get('content') or ''}"
            for item in search_results
        ]
    )
    keyword_candidates.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", corpus))
    focus_terms = [
        "爆款",
        "趋势",
        "题材",
        "标签",
        "悬疑",
        "奇幻",
        "科幻",
        "都市",
        "爽文",
        "系统",
        "重生",
        "群像",
        "短剧",
        "情绪",
        "反转",
        "升级",
    ]
    keyword_candidates.extend([term for term in focus_terms if term in corpus])
    return _dedupe(keyword_candidates, 24)


def _build_trend_insights(query_text: str, search_results: list[dict]) -> tuple[list[dict], list[str], list[dict]]:
    topics: list[dict] = []
    directions: list[dict] = []
    sources: list[dict] = []

    for index, item in enumerate(search_results[:8], start=1):
        title = _compact_text(item.get("title"), 120)
        content = _compact_text(item.get("content"), 360)
        url = _compact_text(item.get("url"), 500)
        score = item.get("score")
        if not title and not content:
            continue

        insight = content or title
        topics.append(
            {
                "rank": index,
                "title": title or f"趋势线索 {index}",
                "insight": insight,
                "url": url,
                "score": score,
            }
        )
        directions.append(
            {
                "title": f"方向 {index}: {title or query_text}",
                "premise": insight,
                "conflict": "把外部热点转译为角色目标、世界规则或阶段性危机。",
                "source_url": url,
            }
        )
        sources.append(
            {
                "title": title or url or f"source-{index}",
                "url": url,
                "snippet": content,
                "score": score,
            }
        )

    if not topics:
        topics.append(
            {
                "rank": 1,
                "title": "未获取到外部趋势结果",
                "insight": "建议稍后重试，或调整搜索查询与搜索深度。",
                "url": "",
                "score": None,
            }
        )
        directions.append(
            {
                "title": "备用方向: 手动补充题材假设",
                "premise": "当前没有搜索证据，先把项目核心卖点拆成可验证假设。",
                "conflict": "缺少外部趋势证据时，避免直接生成大量资产。",
                "source_url": "",
            }
        )

    return topics, _extract_tags(query_text, search_results), directions


def list_trends(db: Session, project_id: int) -> list[TrendExploration]:
    return list(
        db.scalars(
            select(TrendExploration)
            .where(TrendExploration.project_id == project_id)
            .order_by(TrendExploration.updated_at.desc())
        )
    )


def create_trend(db: Session, project_id: int, payload: TrendExplorationCreate) -> TrendExploration:
    trend = TrendExploration(project_id=project_id, **payload.model_dump())
    db.add(trend)
    db.commit()
    db.refresh(trend)
    return trend


def execute_trend_exploration(
    db: Session,
    project_id: int,
    title: str,
    query_text: str,
    source_scope: str = "web",
    search_depth: str = "advanced",
    max_results: int = 5,
    allow_builtin_fallback: bool = False,
) -> TrendExploration:
    """三路搜索引擎轮询 + 离线兜底，绝不死磕单点：

    1) **Tavily**（主）—— 失败（key 未配 / 网络 / 5xx）→ 2
    2) **Firecrawl `/v2/search`**（fallback 1）—— 失败 → 3
    3) **DuckDuckGo 公开搜索**（fallback 2，无需 key）—— 失败 → 4
    4) **内置离线关键词**（终极兜底）—— 永远不阻塞 workflow
    """
    tavily_client = build_tavily_client()
    firecrawl_client = build_firecrawl_client()
    duckduckgo_client = build_duckduckgo_client()

    search_response: dict = {"results": [], "source": "none", "query": query_text, "fallback_chain": []}

    # ── 1) Tavily ─────────────────────────────────────────────────────
    if tavily_client is not None:
        try:
            logger.info("[1/3 Tavily] searching: %s", query_text)
            tavily_resp = tavily_client.search(
                query=query_text,
                search_depth=search_depth,
                max_results=max_results,
            )
            tavily_results = tavily_resp.get("results", []) if isinstance(tavily_resp, dict) else []
            if isinstance(tavily_results, list) and tavily_results:
                search_response = {
                    "source": "tavily",
                    "query": query_text,
                    "results": tavily_results,
                    "fallback_chain": ["tavily"],
                }
                logger.info("[1/3 Tavily] ✓ 拿到 %s 条结果", len(tavily_results))
            else:
                search_response["fallback_chain"].append("tavily:empty")
                logger.warning("[1/3 Tavily] ⚠ 返回 0 条结果，切下一个")
        except Exception as exc:
            logger.error("[1/3 Tavily] ✗ 失败: %s", exc, exc_info=True)
            search_response["fallback_chain"].append(f"tavily:error:{type(exc).__name__}")
    else:
        logger.warning("[1/3 Tavily] ✗ 未配置 TAVILY_KEY，跳过")
        search_response["fallback_chain"].append("tavily:no_key")

    # ── 2) Firecrawl search ──────────────────────────────────────────
    if not search_response.get("results"):
        if firecrawl_client is not None:
            try:
                logger.info("[2/3 Firecrawl] searching: %s", query_text)
                fc_resp = firecrawl_client.search(query=query_text, limit=max_results, lang="zh", country="CN")
                fc_results = _extract_firecrawl_results(fc_resp)
                if fc_results:
                    search_response = {
                        "source": "firecrawl",
                        "query": query_text,
                        "results": fc_results,
                        "fallback_chain": search_response["fallback_chain"] + ["firecrawl"],
                    }
                    logger.info("[2/3 Firecrawl] ✓ 拿到 %s 条结果", len(fc_results))
                else:
                    search_response["fallback_chain"].append("firecrawl:empty")
                    logger.warning("[2/3 Firecrawl] ⚠ 返回 0 条结果，切下一个")
            except Exception as exc:
                logger.error("[2/3 Firecrawl] ✗ 失败: %s", exc, exc_info=True)
                search_response["fallback_chain"].append(f"firecrawl:error:{type(exc).__name__}")
        else:
            logger.warning("[2/3 Firecrawl] ✗ 未配置 FIRECRAWL_KEY，跳过")
            search_response["fallback_chain"].append("firecrawl:no_key")

    # ── 3) DuckDuckGo 公开搜索 ────────────────────────────────────────
    if not search_response.get("results"):
        try:
            logger.info("[3/3 DuckDuckGo] searching: %s", query_text)
            ddg_resp = duckduckgo_client.search(query=query_text, max_results=max_results)
            ddg_results = ddg_resp.get("results", []) if isinstance(ddg_resp, dict) else []
            if ddg_results:
                search_response = {
                    "source": "duckduckgo",
                    "query": query_text,
                    "results": ddg_results,
                    "fallback_chain": search_response["fallback_chain"] + ["duckduckgo"],
                }
                logger.info("[3/3 DuckDuckGo] ✓ 拿到 %s 条结果", len(ddg_results))
            else:
                search_response["fallback_chain"].append("duckduckgo:empty")
                logger.warning("[3/3 DuckDuckGo] ⚠ 返回 0 条结果，切离线兜底")
        except Exception as exc:
            logger.error("[3/3 DuckDuckGo] ✗ 失败: %s", exc, exc_info=True)
            search_response["fallback_chain"].append(f"duckduckgo:error:{type(exc).__name__}")

    # ── 4) 离线关键词兜底（永远不阻塞）────────────────────────────
    if not search_response.get("results"):
        if not allow_builtin_fallback:
            logger.warning(
                "[offline fallback] 3 路搜索引擎全部失败，使用内置 FALLBACK_TREND_KEYWORDS"
            )
        search_response = _fallback_search_response(query_text, max_results)
        search_response["fallback_chain"] = search_response.get("fallback_chain", []) + ["offline_keywords"]

    search_results = search_response.get("results", [])
    if not isinstance(search_results, list):
        search_results = []

    scraped_results: list[dict] = []
    if firecrawl_client is None:
        logger.info("Firecrawl key is not configured, skipping optional scrape")
    else:
        for result in search_results[:3]:
            url = result.get("url")
            if not url:
                continue
            try:
                scraped_results.append(
                    {
                        "url": url,
                        "scrape": firecrawl_client.scrape(url),
                    }
                )
            except Exception as exc:
                logger.error("Service Firecrawl failed: %s", exc, exc_info=True)
                scraped_results.append(
                    {
                        "url": url,
                        "error": str(exc),
                    }
                )
                logger.warning("Skipping Firecrawl result and keeping search summary only: url=%s", url)

    topics, tags, directions = _build_trend_insights(query_text, search_results)

    if search_response.get("source") == "fallback" or "offline_keywords" in search_response.get("fallback_chain", []):
        tags = _dedupe(tags + FALLBACK_TREND_KEYWORDS, 24)
        directions.append(
            {
                "title": "离线降级方向: 高概念强冲突开局",
                "premise": "外部搜索不可用时，优先选择能在前三章展示明确钩子的题材组合。",
                "conflict": "主角目标与世界规则直接冲突，推动连续升级。",
                "source_url": "",
            }
        )

    trend = TrendExploration(
        project_id=project_id,
        title=title,
        source_scope=source_scope,
        query_text=query_text,
        raw_findings=json.dumps(
            {
                "query": query_text,
                "source": search_response.get("source", "none"),
                "fallback_chain": search_response.get("fallback_chain", []),
                "sources": [
                    {
                        "title": topic["title"],
                        "url": topic["url"],
                        "snippet": topic["insight"],
                        "score": topic["score"],
                    }
                    for topic in topics
                ],
                "search_response": _truncate_for_db(
                    {k: v for k, v in search_response.items() if k != "results"},
                    limit=4000,
                ),
                "firecrawl": _truncate_for_db(scraped_results, limit=2000, list_limit=2),
            },
            ensure_ascii=False,
        ),
        extracted_topics=json.dumps(topics[:10], ensure_ascii=False),
        extracted_tags=json.dumps(tags[:20], ensure_ascii=False),
        suggested_directions=json.dumps(directions[:10], ensure_ascii=False),
        status="completed",
    )
    db.add(trend)
    db.commit()
    db.refresh(trend)
    return trend


def _truncate_for_db(value, limit: int = 4000, list_limit: int = 5):
    """把 Tavily/Firecrawl 的大块响应（可能 50K+ 字符）截断到 MySQL Text 列安全范围。

    关键数据已存在 extracted_topics/tags/suggested_directions 里，raw_findings 只用于审计。
    """
    import copy as _copy

    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [truncated {len(value) - limit} chars]"
    if isinstance(value, list):
        out = value[:list_limit]
        if len(value) > list_limit:
            out.append(f"... [truncated {len(value) - list_limit} items]")
        return [_truncate_for_db(item, limit, list_limit) for item in out]
    if isinstance(value, dict):
        return {k: _truncate_for_db(v, limit, list_limit) for k, v in _copy.copy(value).items()}
    return value


def _extract_firecrawl_results(fc_resp: dict) -> list[dict]:
    """Firecrawl v2 search 响应归一化为 {title, url, content, score} 列表。"""
    if not isinstance(fc_resp, dict):
        return []
    # Firecrawl v2 search 响应常见字段：data（list）、web（list）；有些版本包在 success/data 里
    data = fc_resp.get("data")
    if not isinstance(data, list):
        data = fc_resp.get("web") or fc_resp.get("results") or []
    if not isinstance(data, list):
        return []
    results: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Firecrawl 标准字段：title / url / description（部分版本 markdown / content）
        title = (item.get("title") or item.get("name") or "").strip()
        url = (item.get("url") or item.get("link") or "").strip()
        content = (
            item.get("description")
            or item.get("snippet")
            or item.get("markdown")
            or item.get("content")
            or ""
        ).strip()
        if not title and not content:
            continue
        if not url:
            continue
        results.append(
            {
                "title": title[:200] or url,
                "url": url,
                "content": content[:600] if isinstance(content, str) else str(content),
                "score": item.get("score") or 0.5,
            }
        )
    return results
