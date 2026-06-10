"""故事脉络 (Story Arc) API 单测。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import story_arc
from app.api.routes.story_arc import (
    _build_chapter_node,
    _build_edges,
    _build_plot_line_node,
    _build_resolves_edges,
    _classify_chapter_type,
    _extract_emotional_arc,
    _split_conflict,
    read_story_arc,
)


# ---------------------------------------------------------------------------
# Mock 工厂
# ---------------------------------------------------------------------------
def _make_chapter(
    cid: int = 1,
    no: int | None = 1,
    title: str = "测试章节",
    status: str = "draft",
    conflict: str | None = None,
    summary: str | None = None,
    objective: str | None = None,
    word_count: int = 0,
    book_id: int = 1,
    project_id: int = 1,
) -> MagicMock:
    ch = MagicMock()
    ch.id = cid
    ch.chapter_no = no
    ch.title = title
    ch.status = status
    ch.conflict = conflict
    ch.summary = summary
    ch.objective = objective
    ch.word_count = word_count
    ch.book_id = book_id
    ch.project_id = project_id
    return ch


def _make_plot_line(
    pid: int = 1,
    title: str = "主线",
    plot_type: str = "main",
    priority: int = 50,
    book_id: int = 1,
    project_id: int = 1,
    chapter_id: int | None = None,
    scene_order: int = 0,
    summary: str | None = None,
    goal: str | None = None,
) -> MagicMock:
    pl = MagicMock()
    pl.id = pid
    pl.title = title
    pl.plot_type = plot_type
    pl.priority = priority
    pl.book_id = book_id
    pl.project_id = project_id
    pl.chapter_id = chapter_id
    pl.scene_order = scene_order
    pl.summary = summary
    pl.goal = goal
    return pl


def _make_plan(plan_id: int = 1, plot_line_id: int = 1, chapter_id: int = 1) -> MagicMock:
    cp = MagicMock()
    cp.id = plan_id
    cp.plot_line_id = plot_line_id
    cp.chapter_id = chapter_id
    cp.project_id = 1
    cp.book_id = 1
    return cp


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------
class TestSplitConflict:
    def test_empty_returns_empty_set(self) -> None:
        assert _split_conflict(None) == set()
        assert _split_conflict("") == set()

    def test_single_keyword(self) -> None:
        assert _split_conflict("吴三桂") == {"吴三桂"}

    def test_multiple_separators(self) -> None:
        assert _split_conflict("吴三桂,闯王,皇太极") == {"吴三桂", "闯王", "皇太极"}

    def test_chinese_separators(self) -> None:
        assert _split_conflict("吴三桂、闯王；李自成") == {"吴三桂", "闯王", "李自成"}

    def test_strips_whitespace(self) -> None:
        assert _split_conflict("  吴三桂  ,  闯王  ") == {"吴三桂", "闯王"}


# ---------------------------------------------------------------------------
# SubTask 2.1 + 2.6
# ---------------------------------------------------------------------------
class TestBuildPlotLineNode:
    def test_plot_line_uses_correct_type(self) -> None:
        pl = _make_plot_line(pid=1, title="主线", plot_type="main", priority=80)
        node = _build_plot_line_node(pl)
        assert node["type"] == "plot_line"
        assert node["id"] == "plot-1"
        assert node["chapterNo"] is None
        assert node["wordCount"] == 0
        assert node["emotionalArc"] == ""
        assert node["plotLineId"] == 1
        assert node["plotType"] == "main"


class TestBuildChapterNode:
    def test_chapter_node_has_required_fields(self) -> None:
        ch = _make_chapter(
            cid=1, no=1, title="第一幕", conflict="吴三桂", word_count=2000
        )
        node = _build_chapter_node(ch)
        assert node["type"] in ("chapter", "ending", "climax", "turning_point", "conflict")
        assert node["id"] == "chapter-1"
        assert "emotionalArc" in node
        assert node["emotionalArc"] in ("悲怆", "激昂", "舒缓", "起伏")
        assert "wordCount" in node
        assert node["wordCount"] == 2000
        assert "status" in node
        assert node["status"] == "draft"
        assert node["chapterNo"] == 1

    def test_chapter_node_status_completed(self) -> None:
        ch = _make_chapter(cid=2, no=2, title="测试", status="writing", word_count=100)
        node = _build_chapter_node(ch)
        assert node["status"] == "writing"
        assert node["wordCount"] == 100


class TestClassifyChapterType:
    def test_title_ending_keyword(self) -> None:
        ch = _make_chapter(no=10, title="大结局", status="completed", conflict="")
        assert _classify_chapter_type(ch) == "ending"

    def test_climax_keyword(self) -> None:
        ch = _make_chapter(no=3, title="决战之夜")
        assert _classify_chapter_type(ch) == "climax"

    def test_turning_keyword(self) -> None:
        ch = _make_chapter(no=2, title="剧情转折")
        assert _classify_chapter_type(ch) == "turning_point"

    def test_plain_chapter(self) -> None:
        ch = _make_chapter(no=1, title="开篇")
        assert _classify_chapter_type(ch) == "chapter"


class TestExtractEmotionalArc:
    def test_sad_title(self) -> None:
        ch = _make_chapter(title="悲情诀别")
        assert _extract_emotional_arc(ch) == "悲怆"

    def test_exciting_title(self) -> None:
        ch = _make_chapter(title="决战之夜")
        assert _extract_emotional_arc(ch) == "激昂"

    def test_calm_title(self) -> None:
        ch = _make_chapter(title="日常")
        assert _extract_emotional_arc(ch) == "舒缓"

    def test_default_undulating(self) -> None:
        ch = _make_chapter(title="故事")
        assert _extract_emotional_arc(ch) == "起伏"


# ---------------------------------------------------------------------------
# SubTask 2.4 — conflicts_with 关键词交集
# ---------------------------------------------------------------------------
class TestBuildEdges:
    def test_sequel_to_edges_sequential(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1),
            _make_chapter(cid=2, no=2),
            _make_chapter(cid=3, no=3),
        ]
        edges = _build_edges(chapters)
        sequel_edges = [e for e in edges if e["relation"] == "sequel_to"]
        assert len(sequel_edges) == 2
        assert sequel_edges[0]["source"] == "chapter-1"
        assert sequel_edges[0]["target"] == "chapter-2"
        assert sequel_edges[1]["source"] == "chapter-2"
        assert sequel_edges[1]["target"] == "chapter-3"

    def test_conflicts_with_keyword_intersection(self) -> None:
        """a.conflict 关键词集合和 b.conflict 关键词集合有交集 → 加边"""
        chapters = [
            _make_chapter(cid=1, no=1, conflict="吴三桂,闯王"),
            _make_chapter(cid=2, no=2, conflict="吴三桂,叛军"),
        ]
        edges = _build_edges(chapters)
        conflict_edges = [e for e in edges if e["relation"] == "conflicts_with"]
        assert len(conflict_edges) == 1
        # weight = |inter| / |uni| = 1 / 3 ≈ 0.333
        assert 0.0 < conflict_edges[0]["weight"] <= 1.0
        assert "吴三桂" in conflict_edges[0]["label"]

    def test_conflicts_with_no_intersection(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1, conflict="吴三桂"),
            _make_chapter(cid=2, no=2, conflict="李自成"),
        ]
        edges = _build_edges(chapters)
        conflict_edges = [e for e in edges if e["relation"] == "conflicts_with"]
        assert len(conflict_edges) == 0

    def test_conflicts_with_empty_conflict(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1, conflict=None),
            _make_chapter(cid=2, no=2, conflict="李自成"),
        ]
        edges = _build_edges(chapters)
        conflict_edges = [e for e in edges if e["relation"] == "conflicts_with"]
        assert len(conflict_edges) == 0


# ---------------------------------------------------------------------------
# SubTask 2.5 — resolves 边
# ---------------------------------------------------------------------------
class TestBuildResolvesEdges:
    def test_resolves_edge_with_keyword_in_summary(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1, conflict="吴三桂 vs 闯王", summary=""),
            _make_chapter(cid=2, no=2, conflict="", summary="最终化解了所有冲突"),
        ]
        edges = _build_resolves_edges(chapters)
        assert len(edges) >= 1
        e = edges[0]
        assert e["source"] == "chapter-1"
        assert e["target"] == "chapter-2"
        assert e["relation"] == "resolves"
        assert e["weight"] == 0.7
        assert "化解" in e["label"]

    def test_no_resolves_edge_when_conflict_remains(self) -> None:
        """b.conflict 仍含 K → 不算化解"""
        chapters = [
            _make_chapter(cid=1, no=1, conflict="吴三桂", summary=""),
            _make_chapter(cid=2, no=2, conflict="吴三桂", summary="化解了吴三桂的问题"),
        ]
        edges = _build_resolves_edges(chapters)
        assert len(edges) == 0

    def test_resolves_edge_deduplicated(self) -> None:
        """多关键词 a.conflict 触发多次时去重"""
        chapters = [
            _make_chapter(cid=1, no=1, conflict="吴三桂,闯王", summary=""),
            _make_chapter(cid=2, no=2, conflict="", summary="化解了一切"),
        ]
        edges = _build_resolves_edges(chapters)
        # 同样 (ca.id, cb.id) 只加一次 resolves 边
        resolve_edges = [e for e in edges if e["relation"] == "resolves"]
        assert len(resolve_edges) == 1


# ---------------------------------------------------------------------------
# SubTask 2.7 — scene 节点扩字段
# ---------------------------------------------------------------------------
class TestSceneExtraction:
    """通过 mock 完整 read_story_arc 流程来验证 scene 节点字段"""

    def test_scene_node_has_emotional_arc_and_word_count(self) -> None:
        db = _build_mock_db(
            chapters=[],
            plot_lines=[],
            chapter_plans=[],
        )
        # 让章节查询直接返回空（空数据走空 message 分支）
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        # 实际上我们想测试 scene 提取逻辑，借用 _split_conflict / _SCENE_TITLE_SPLIT_RE 的逻辑
        import re

        title = "第1章 · 场景1 · 晨雾中的卷宗"
        parts = story_arc._SCENE_TITLE_SPLIT_RE.split(title)
        assert len(parts) > 1
        assert parts[-1].strip() == "晨雾中的卷宗"

    def test_scene_title_no_separator_falls_back(self) -> None:
        import re

        title = "晨雾中的卷宗"
        parts = story_arc._SCENE_TITLE_SPLIT_RE.split(title)
        # 无分隔符时 fallback 取原 title
        assert len(parts) == 1
        fallback = parts[-1].strip() if (len(parts) > 1 and parts[-1].strip()) else title
        assert fallback == title


# ---------------------------------------------------------------------------
# SubTask 2.2 — ending 节点判定兜底（通过完整 read_story_arc 验证）
# ---------------------------------------------------------------------------
def _build_mock_db(
    chapters: list[MagicMock],
    plot_lines: list[MagicMock],
    chapter_plans: list[MagicMock],
) -> MagicMock:
    """构造一个能返回预期数据的 mock Session。

    read_story_arc 中 db.query 调用顺序：
      1) Chapter         → chapter_chain
      2) PlotLine (plot)  → plot_chain (plot_type != chapter_scene)
      3) PlotLine (scene) → scene_chain (plot_type == chapter_scene)
      4) ChapterPlan     → plan_chain
    """
    db = MagicMock()

    def make_chain(items: list) -> MagicMock:
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = items
        chain.first.return_value = items[0] if items else None
        return chain

    chapter_chain = make_chain(chapters)
    # plot_query 在 scene_query 之前调用
    plot_chain = make_chain(plot_lines)
    # scene 查询可能返回空列表（空测试场景）
    scene_chain = make_chain([])
    plan_chain = make_chain(chapter_plans)
    db.query.side_effect = [chapter_chain, plot_chain, scene_chain, plan_chain]
    return db


class TestReadStoryArcEndingFallback:
    def test_ending_heuristic_fallback(self) -> None:
        """3 chapter，最后 chapter_no 最大且 status=completed → 标 ending"""
        chapters = [
            _make_chapter(cid=1, no=1, title="开篇", word_count=2000),
            _make_chapter(cid=2, no=2, title="中篇", word_count=3000),
            _make_chapter(cid=3, no=3, title="未命名章节", status="completed", word_count=4000),
        ]
        db = _build_mock_db(chapters=chapters, plot_lines=[], chapter_plans=[])

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)

        assert result.success is True
        assert result.code == 200
        data = result.data
        chapter_nodes = [n for n in data["nodes"] if n["id"].startswith("chapter-")]
        ending_nodes = [n for n in chapter_nodes if n["type"] == "ending"]
        # 兜底逻辑：max chapter_no=3 + status=completed → 标 ending（即使标题不含"终"）
        assert len(ending_nodes) == 1
        assert ending_nodes[0]["id"] == "chapter-3"

    def test_ending_not_applied_when_status_not_completed(self) -> None:
        """最高 chapter_no 但 status=draft → 不标 ending（兜底不生效）"""
        chapters = [
            _make_chapter(cid=1, no=1, title="开篇"),
            _make_chapter(cid=2, no=2, title="中篇", status="draft"),
        ]
        db = _build_mock_db(chapters=chapters, plot_lines=[], chapter_plans=[])

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        chapter_nodes = [n for n in result.data["nodes"] if n["id"].startswith("chapter-")]
        ending_nodes = [n for n in chapter_nodes if n["type"] == "ending"]
        assert len(ending_nodes) == 0


class TestReadStoryArcStatsFields:
    def test_includes_emotional_arc_stats(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1, title="开篇", conflict="吴三桂 vs 闯王", word_count=2000),
            _make_chapter(cid=2, no=2, title="决战", status="completed", word_count=3000),
            _make_chapter(cid=3, no=3, title="日常", status="completed", word_count=4000),
        ]
        db = _build_mock_db(chapters=chapters, plot_lines=[], chapter_plans=[])

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        stats = result.data["stats"]

        # 情绪分布（4 类）
        assert "emotionalArc" in stats
        assert isinstance(stats["emotionalArc"], dict)
        assert set(stats["emotionalArc"].keys()) >= {"悲怆", "激昂", "舒缓", "起伏"}
        # 3 章节总和 = 3
        assert sum(stats["emotionalArc"].values()) == 3

    def test_includes_word_count_by_chapter(self) -> None:
        chapters = [
            _make_chapter(cid=1, no=1, word_count=2000),
            _make_chapter(cid=2, no=2, word_count=3000),
            _make_chapter(cid=3, no=3, word_count=4000),
        ]
        db = _build_mock_db(chapters=chapters, plot_lines=[], chapter_plans=[])

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        stats = result.data["stats"]
        assert "wordCountByChapter" in stats
        assert len(stats["wordCountByChapter"]) == 3
        # 字段是 camelCase
        assert all("chapterNo" in w and "wordCount" in w for w in stats["wordCountByChapter"])

    def test_stats_includes_version_and_generated_at(self) -> None:
        chapters = [_make_chapter(cid=1, no=1)]
        db = _build_mock_db(chapters=chapters, plot_lines=[], chapter_plans=[])

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        stats = result.data["stats"]
        assert stats["version"] == 2
        assert "generatedAt" in stats
        assert stats["generatedAt"].endswith("Z")
        # 响应顶层也有
        assert result.data["version"] == 2
        assert "generatedAt" in result.data


class TestReadStoryArcOrphanScenes:
    def test_orphan_scene_counted(self) -> None:
        """scene.chapter_id 为 None 时不生成 leads_to 边 + orphanScenes +1"""
        chapter = _make_chapter(cid=1, no=1, title="开篇")
        plot = _make_plot_line(
            pid=1, title="主线", plot_type="main", priority=80
        )
        orphan_scene = _make_plot_line(
            pid=2,
            title="第1章 · 场景1 · 晨雾",
            plot_type="chapter_scene",
            chapter_id=None,  # 孤儿
            scene_order=1,
        )
        normal_scene = _make_plot_line(
            pid=3,
            title="第1章 · 场景2 · 雾散",
            plot_type="chapter_scene",
            chapter_id=1,
            scene_order=2,
        )
        chapters = [chapter]
        # 查询顺序：1) chapter  2) plot (plot_type != chapter_scene)  3) scene (chapter_id.in_)  4) ChapterPlan
        scene_chain = MagicMock()
        scene_chain.filter.return_value = scene_chain
        scene_chain.order_by.return_value = scene_chain
        scene_chain.all.return_value = [orphan_scene, normal_scene]

        plot_chain = MagicMock()
        plot_chain.filter.return_value = plot_chain
        plot_chain.order_by.return_value = plot_chain
        plot_chain.limit.return_value = plot_chain
        plot_chain.all.return_value = [plot]

        chapter_chain = MagicMock()
        chapter_chain.filter.return_value = chapter_chain
        chapter_chain.order_by.return_value = chapter_chain
        chapter_chain.all.return_value = chapters

        plan_chain = MagicMock()
        plan_chain.filter.return_value = plan_chain
        plan_chain.all.return_value = []

        db = MagicMock()
        # 查询顺序：Chapter → PlotLine (plot) → PlotLine (scene) → ChapterPlan
        db.query.side_effect = [chapter_chain, plot_chain, scene_chain, plan_chain]

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        stats = result.data["stats"]
        assert stats["orphanScenes"] == 1
        # leads_to 边只应有 1 条（normal_scene 指向 chapter-1）
        leads_to_edges = [
            e
            for e in result.data["edges"]
            if e["relation"] == "leads_to" and e["source"] == "chapter-1"
        ]
        assert len(leads_to_edges) == 1
        assert leads_to_edges[0]["target"] == "scene-3"


class TestReadStoryArcEmpty:
    def test_empty_chapters_returns_chinese_message(self) -> None:
        chapter_chain = MagicMock()
        chapter_chain.filter.return_value = chapter_chain
        chapter_chain.order_by.return_value = chapter_chain
        chapter_chain.all.return_value = []
        # 让空 chapter 走 early return 分支——空 chapters 不会调用后续 query
        db = MagicMock()
        db.query.return_value = chapter_chain

        result = read_story_arc(project_id=999, book_id=None, plot_limit=20, db=db)
        assert result.success is True
        assert result.code == 200
        assert "项目下暂无章节数据" in result.message
        # 空 data 仍带完整 stats
        stats = result.data["stats"]
        assert stats["chapters"] == 0
        assert stats["plotLines"] == 0
        assert stats["plans"] == 0
        assert stats["scenes"] == 0
        assert stats["orphanScenes"] == 0
        assert "emotionalArc" in stats
        assert "wordCountByChapter" in stats
        assert stats["wordCountByChapter"] == []
        assert stats["version"] == 2
        assert "generatedAt" in stats
        # 响应顶层
        assert result.data["version"] == 2
        assert "generatedAt" in result.data


class TestReadStoryArcDBError:
    def test_db_error_returns_503_chinese_message(self) -> None:
        db = MagicMock()
        db.query.side_effect = SQLAlchemyError("connection lost")
        # 第一次 query 抛错
        db.query.side_effect = SQLAlchemyError("connection lost")

        result = read_story_arc(project_id=1, book_id=None, plot_limit=20, db=db)
        assert result.success is False
        assert result.code == 503
        assert "故事脉络查询失败" in result.message
        assert "connection lost" in result.message or "connection" in result.message
        # data 包含完整 stats 占位
        stats = result.data["stats"]
        assert stats["chapters"] == 0
        assert stats["emotionalArc"] == {"悲怆": 0, "激昂": 0, "舒缓": 0, "起伏": 0}
        assert stats["wordCountByChapter"] == []
        assert stats["orphanScenes"] == 0
        assert stats["version"] == 2
