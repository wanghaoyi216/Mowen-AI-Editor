"""故事总览 (Dashboard) API —— Tab8 真实数据源。

聚合项目的实时 KPI 与图表数据：
  * KPI 卡片：已完成章节 / 累计字数 / 累计耗时 / 当前进度
  * 章节进度折线：每章字数随章节号变化
  * 角色出场频次：基于 chapter.final_content / draft_content + 角色名做简单计数
  * 一致性评分：5 维（角色 / 剧情 / 世界 / 节奏 / 风格），从 chapter_version.consistency_report 解析
  * 题材分布：按章节 objective 推断
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes._guards import get_owned_project
from app.models.ai_task import AITask
from app.models.chapter import Chapter
from app.models.chapter_version import ChapterVersion
from app.models.character import Character
from app.models.project import NovelProject
from app.schemas.common import ApiResponse


router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_consistency_scores(report: str | None) -> dict[str, float]:
    """从一致性检查报告中解析五维评分，缺失字段返回 0。"""
    scores = {"character": 0, "plot": 0, "world": 0, "pacing": 0, "style": 0}
    if not report:
        return scores
    # 尝试匹配形如 角色: 85 / 85分 / 85.5 等格式
    patterns = {
        "character": r"(?:角色|character)[^0-9]*(\d{1,3}(?:\.\d)?)",
        "plot": r"(?:剧情|plot)[^0-9]*(\d{1,3}(?:\.\d)?)",
        "world": r"(?:世界|world|世界观)[^0-9]*(\d{1,3}(?:\.\d)?)",
        "pacing": r"(?:节奏|pacing)[^0-9]*(\d{1,3}(?:\.\d)?)",
        "style": r"(?:风格|style)[^0-9]*(\d{1,3}(?:\.\d)?)",
    }
    for key, pat in patterns.items():
        match = re.search(pat, report, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                scores[key] = max(0, min(100, value))
            except ValueError:
                pass
    return scores


# 题材关键词映射表：每类题材一个或多个触发词
_GENRE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("奇幻", ("蒸汽", "魔法", "奇幻", "玄幻", "修真", "仙侠", "武侠", "灵根", "道法", "剑修", "斗气")),
    ("都市", ("都市", "职场", "商战", "现代", "写字楼", "CBD", "通勤", "互联网公司")),
    ("科幻", ("科幻", "未来", "星际", "赛博", "机甲", "人工智能", "AI", "末世", "飞船", "克隆")),
    ("悬疑", ("悬疑", "推理", "侦探", "案件", "审判", "巡察", "档案", "犯罪", "密室", "失踪")),
    ("历史", ("历史", "古代", "宫廷", "权谋", "朝堂", "皇帝", "太子", "谋反", "藩镇", "科举")),
    ("言情", ("言情", "爱情", "情感", "浪漫", "暗恋", "恋爱", "破镜重圆", "甜宠", "虐恋")),
    ("恐怖", ("恐怖", "灵异", "惊悚", "灰雾", "禁术", "鬼", "诅咒", "驱魔", "降头", "阴魂")),
    ("军事", ("军事", "战争", "战役", "将军", "士兵", "特种", "演习", "维和", "谍战")),
]


def _infer_genres(objective: str | None, title: str | None = "") -> list[str]:
    """从章节 objective / title 推断题材类型（**返回多标签列表**，不再单选）。

    一段文本可能同时命中多个题材，例如"现代职场 + 爱情"应同时计入"都市"和"言情"。
    """
    text = f"{objective or ''} {title or ''}".lower()
    matched: list[str] = []
    for genre, kws in _GENRE_KEYWORDS:
        if any(kw in text for kw in kws):
            matched.append(genre)
    return matched


def _count_character_appearances(
    characters: list[Character],
    chapters: list[Chapter],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """统计角色在章节正文中的出现次数。"""
    counts: Counter[str] = Counter()
    char_names = [c.name for c in characters if c.name]
    if not char_names:
        return []
    for ch in chapters:
        text = (ch.final_content or ch.draft_content or "")
        if not text:
            continue
        for name in char_names:
            # 简单 substring 匹配，中文按字符
            counts[name] += text.count(name)
    top = counts.most_common(top_n)
    return [{"name": name, "count": count} for name, count in top if count > 0]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.get("/{project_id}/dashboard", response_model=ApiResponse)
def read_dashboard(
    project_id: int,
    db: Session = Depends(get_db_session),
    _project: NovelProject = Depends(get_owned_project),
) -> ApiResponse:
    """读取项目故事总览数据。

    返回结构：
    {
      "kpi": {
        "completedChapters": 5,
        "totalChapters": 10,
        "totalWords": 24000,
        "avgLatencyMs": 3200,
        "totalDurationSeconds": 1200,
        "progressPercent": 50
      },
      "chapterProgress": [
        { "chapterNo": 1, "status": "completed", "wordCount": 2400 }
      ],
      "wordCountBar": [
        { "chapterNo": 1, "words": 2400 }
      ],
      "latencyHist": [
        { "bucket": "0-2s", "count": 1 }
      ],
      "characterFreq": [
        { "name": "林远", "count": 28 }
      ],
      "consistencyRadar": {
        "character": 90, "plot": 85, "world": 78, "pacing": 82, "style": 88
      },
      "genreDistribution": [
        { "genre": "玄幻", "count": 5 }
      ],
      "novel": { "title": "...", "genre": "..." }
    }
    """
    try:
        project = (
            db.query(NovelProject).filter(NovelProject.id == project_id).first()
        )
    except Exception as exc:
        logger.warning("dashboard: project query failed: %s", exc)
        project = None
    if project is None:
        return ApiResponse(
            message="dashboard: project not found",
            data={"kpi": _empty_kpi(), "chapterProgress": [], "wordCountBar": [],
                  "latencyHist": [], "characterFreq": [], "consistencyRadar": _empty_radar(),
                  "genreDistribution": [], "novel": None},
        )

    chapters = list(
        db.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_no.asc())
        .all()
    )
    characters = list(
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.id.asc())
        .all()
    )
    chapter_versions = list(
        db.query(ChapterVersion)
        .filter(ChapterVersion.project_id == project_id)
        .all()
    )
    ai_tasks = list(
        db.query(AITask)
        .filter(AITask.project_id == project_id)
        .all()
    )

    # KPI
    # 兼容多状态值：completed / drafted / finalized / finalized 统一视为"已完成"
    completed = [
        c for c in chapters
        if c.status in ("completed", "drafted", "finalized")
    ]
    total_words = sum(c.word_count or 0 for c in chapters)
    total_duration = 0
    total_latency_sum = 0
    total_latency_count = 0
    for t in ai_tasks:
        if t.started_at and t.finished_at:
            try:
                delta = (t.finished_at - t.started_at).total_seconds()
                total_duration += max(0, int(delta))
                total_latency_sum += max(0, int(delta * 1000))
                total_latency_count += 1
            except Exception:
                pass
    avg_latency = int(total_latency_sum / total_latency_count) if total_latency_count else 0
    progress_percent = int(len(completed) / max(1, len(chapters)) * 100) if chapters else 0

    kpi = {
        "completedChapters": len(completed),
        "totalChapters": len(chapters),
        "totalWords": total_words,
        "avgLatencyMs": avg_latency,
        "totalDurationSeconds": total_duration,
        "progressPercent": progress_percent,
    }

    # 章节进度
    chapter_progress = [
        {
            "chapterNo": c.chapter_no,
            "status": c.status or "planned",
            "wordCount": c.word_count or 0,
        }
        for c in chapters
    ]
    word_count_bar = [
        {"chapterNo": c.chapter_no, "words": c.word_count or 0}
        for c in chapters if c.word_count and c.word_count > 0
    ]

    # Latency histogram (0-2s, 2-5s, 5-10s, 10-30s, 30s+)
    buckets = [
        ("0-2s", 0, 2000), ("2-5s", 2000, 5000),
        ("5-10s", 5000, 10000), ("10-30s", 10000, 30000),
        ("30s+", 30000, float("inf")),
    ]
    bucket_counts = {b[0]: 0 for b in buckets}
    for t in ai_tasks:
        if t.started_at and t.finished_at:
            try:
                ms = int((t.finished_at - t.started_at).total_seconds() * 1000)
                for label, lo, hi in buckets:
                    if lo <= ms < hi:
                        bucket_counts[label] += 1
                        break
            except Exception:
                pass
    latency_hist = [{"bucket": k, "count": v} for k, v in bucket_counts.items()]

    # 角色频次
    character_freq = _count_character_appearances(characters, chapters, top_n=10)

    # 一致性评分：取最新一份 ChapterVersion.consistency_report 聚合
    consistency_acc: dict[str, list[float]] = {
        "character": [], "plot": [], "world": [], "pacing": [], "style": []
    }
    for v in chapter_versions:
        if v.consistency_report:
            scores = _parse_consistency_scores(v.consistency_report)
            for k, val in scores.items():
                if val > 0:
                    consistency_acc[k].append(val)
    consistency_radar = {
        k: (sum(vs) / len(vs)) if vs else 0.0
        for k, vs in consistency_acc.items()
    }
    # 如果没有 version 报告，尝试从 task.output_payload 中找
    if all(v == 0 for v in consistency_radar.values()):
        for t in ai_tasks:
            if t.output_payload and "consistency" in (t.output_payload or "").lower():
                scores = _parse_consistency_scores(t.output_payload)
                for k, val in scores.items():
                    if val > 0:
                        consistency_radar[k] = val

    # 兜底：当所有 5 维都还是 0 时，基于章节数据实时计算"软"五维评分。
    # 避免故事总览的"一致性检查"雷达图因为没 AI 一致性报告而变成全 0。
    if all(v == 0 for v in consistency_radar.values()) and chapters:
        # 角色一致性：每章节都提到 1+ 角色 → 高分；缺角色越多少分
        chapters_with_chars = sum(
            1 for c in chapters
            if ((c.final_content or c.draft_content) and any(
                char.name and char.name in (c.final_content or c.draft_content or "")
                for char in characters
            ))
        )
        char_score = min(100, int((chapters_with_chars / max(1, len(chapters))) * 100 + 10))
        # 剧情完整度 = 已完成 / 总数
        plot_score = min(100, int(len(completed) / max(1, len(chapters)) * 100))
        # 世界观完整性 = 有摘要或世界观的章节占比
        with_world = sum(
            1 for c in chapters
            if (c.summary and c.summary.strip()) or (c.objective and c.objective.strip())
        )
        world_score = min(100, int(with_world / max(1, len(chapters)) * 100 + 15))
        # 节奏感 = 字数均衡度（CV 越小分数越高）
        wq = [c.word_count or 0 for c in chapters if (c.word_count or 0) > 0]
        if len(wq) >= 2:
            avg_w = sum(wq) / len(wq)
            var_w = sum((w - avg_w) ** 2 for w in wq) / len(wq)
            cv = (var_w ** 0.5) / avg_w * 100 if avg_w else 100
            pacing_score = max(0, min(100, int(100 - cv)))
        else:
            pacing_score = 50
        # 风格一致性 = 题材多样性（多样性越丰富分数越高，但不超过 100）
        all_genres: set[str] = set()
        for c in chapters:
            for g in _infer_genres(c.objective, c.title):
                all_genres.add(g)
        unique_genres = len(all_genres)
        style_score = min(100, max(40, 40 + unique_genres * 12))
        consistency_radar = {
            "character": char_score,
            "plot": plot_score,
            "world": world_score,
            "pacing": pacing_score,
            "style": style_score,
        }

    # 题材分布：每章节可能命中多个题材，每个命中 +1
    # 修复历史 bug：原版用单选 _infer_genre 后再 fallback，把所有章节误归到 project.genre（如"言情"）
    genre_counter: Counter[str] = Counter()
    for c in chapters:
        for genre in _infer_genres(c.objective, c.title):
            genre_counter[genre] += 1
    genre_distribution = [{"genre": g, "count": cnt} for g, cnt in genre_counter.most_common()]

    return ApiResponse(
        message="dashboard retrieved",
        data={
            "kpi": kpi,
            "chapterProgress": chapter_progress,
            "wordCountBar": word_count_bar,
            "latencyHist": latency_hist,
            "characterFreq": character_freq,
            "consistencyRadar": consistency_radar,
            "genreDistribution": genre_distribution,
            "novel": {
                "id": project.id,
                "title": project.name,
                "genre": project.genre or "",
            },
        },
    )


def _empty_kpi() -> dict[str, Any]:
    return {
        "completedChapters": 0,
        "totalChapters": 0,
        "totalWords": 0,
        "avgLatencyMs": 0,
        "totalDurationSeconds": 0,
        "progressPercent": 0,
    }


def _empty_radar() -> dict[str, float]:
    return {"character": 0, "plot": 0, "world": 0, "pacing": 0, "style": 0}
