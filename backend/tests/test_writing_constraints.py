"""Tests for project writing-constraint enforcement.

覆盖三件事，对应用户的核心诉求"AI 按设定字数/风格创作、不跑题、按当前字数判断怎么写"：

1. ``count_words``：中英文混排字数统计正确。
2. ``build_constraint_block``：把题材/风格/基调/字数渲染进 prompt。
3. ``generate_chapter_draft``：真正把项目约束注入到 LLM prompt，并在草稿
   过短时驱动续写补足到目标字数下限。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.project import NovelProject
from app.services import chapter_ai_service
from app.services.writing_constraints_service import (
    build_constraint_block,
    count_words,
    load_project_constraints,
)


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _fresh_db() -> Generator[Session, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# count_words
# ---------------------------------------------------------------------------

def test_count_words_cjk_and_latin():
    assert count_words("你好世界") == 4
    assert count_words("hello world") == 2
    # 4 个汉字 + 2 个拉丁词(world/123)
    assert count_words("你好世界 world 123") == 6
    assert count_words("") == 0
    assert count_words(None) == 0
    # 标点不计入
    assert count_words("他说：“走吧。”") == 4


# ---------------------------------------------------------------------------
# build_constraint_block
# ---------------------------------------------------------------------------

def test_constraint_block_contains_style_genre_and_word_budget():
    for db in _fresh_db():
        project = NovelProject(
            name="测试项目",
            genre="悬疑推理",
            theme="复仇与救赎",
            writing_style="冷峻硬核",
            tone="黑暗",
            target_audience="成人向",
            min_words_per_chapter=3000,
            max_words_per_chapter=5000,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        constraints = load_project_constraints(db, project.id)
        block = build_constraint_block(constraints, word_target=4000, current_words=1200)

        # 风格/题材/基调/受众/主题都必须出现在约束块里
        assert "悬疑推理" in block
        assert "复仇与救赎" in block
        assert "冷峻硬核" in block
        assert "黑暗" in block
        assert "成人向" in block
        # 字数预算 + 当前字数反馈
        assert "4000" in block
        assert "3000" in block and "5000" in block
        assert "1200" in block  # 当前已写字数
        # 不跑题约束
        assert "跑题" in block


def test_load_constraints_missing_project_uses_defaults():
    for db in _fresh_db():
        constraints = load_project_constraints(db, 999)
        assert constraints.min_words_per_chapter == 2000
        assert constraints.max_words_per_chapter == 4000
        assert constraints.language == "zh-CN"


# ---------------------------------------------------------------------------
# generate_chapter_draft: 约束注入 + 字数强制
# ---------------------------------------------------------------------------

def _seed_project_and_chapter(db: Session) -> int:
    project = NovelProject(
        name="字数强制测试",
        genre="玄幻",
        writing_style="网文爽文",
        tone="热血",
        min_words_per_chapter=100,
        max_words_per_chapter=200,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    chapter = Chapter(
        project_id=project.id,
        chapter_no=1,
        title="开篇",
        summary="主角觉醒",
        status="planned",
        word_count=0,
        version=1,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    plan = ChapterPlan(
        project_id=project.id,
        chapter_id=chapter.id,
        title="开篇",
        design_brief="主角在废墟中觉醒异能。",
        beat_sheet="1. 醒来 2. 发现异能 3. 遭遇危机",
        asset_summary="角色：主角",
        status="designed",
    )
    db.add(plan)
    db.commit()
    return chapter.id


def test_generate_draft_injects_constraints_into_prompt(monkeypatch):
    captured: dict = {}

    def fake_openrouter(system_prompt, user_prompt, preferred_keywords=None, **kwargs):
        # 记录第一次（主创作）调用的 prompt
        if "first_prompt" not in captured:
            captured["first_prompt"] = user_prompt
            captured["role"] = kwargs.get("role")
        return {
            "model": {"id": "test-model"},
            "completion": {"choices": [{"message": {"content": "他猛地睁开眼，异能在指尖炸裂开来。" * 30}}]},
        }

    monkeypatch.setattr(chapter_ai_service, "generate_with_openrouter", fake_openrouter)
    monkeypatch.setattr(chapter_ai_service, "sync_chapter_to_neo4j", lambda *_a, **_k: False)

    for db in _fresh_db():
        chapter_id = _seed_project_and_chapter(db)
        chapter = chapter_ai_service.generate_chapter_draft(db, project_id=1, chapter_id=chapter_id)

        # 约束确实进了 prompt
        assert "网文爽文" in captured["first_prompt"]
        assert "玄幻" in captured["first_prompt"]
        assert "字数" in captured["first_prompt"]
        assert captured["role"] == "creator"
        # word_count 用的是 count_words 而非 len()
        assert chapter.word_count == count_words(chapter.draft_content)
        assert chapter.status == "drafted"


def test_generate_draft_enforces_word_target_by_continuation(monkeypatch):
    calls = {"n": 0}

    def fake_openrouter(system_prompt, user_prompt, preferred_keywords=None, **kwargs):
        calls["n"] += 1
        # 第一次产出过短正文（远低于 100 字下限），逼出续写
        if calls["n"] == 1:
            content = "短。"
        else:
            # 续写补足：返回一段足够长的新内容（不与原文重复）
            content = "随后他踏入秘境深处，机关重重危机四伏，每一步都步步惊心。" * 10
        return {
            "model": {"id": "test-model"},
            "completion": {"choices": [{"message": {"content": content}}]},
        }

    monkeypatch.setattr(chapter_ai_service, "generate_with_openrouter", fake_openrouter)
    monkeypatch.setattr(chapter_ai_service, "sync_chapter_to_neo4j", lambda *_a, **_k: False)

    for db in _fresh_db():
        chapter_id = _seed_project_and_chapter(db)
        chapter = chapter_ai_service.generate_chapter_draft(db, project_id=1, chapter_id=chapter_id)

        # 触发了至少一次续写
        assert calls["n"] >= 2
        # 最终字数达到下限（min_words=100）
        assert chapter.word_count >= 100
