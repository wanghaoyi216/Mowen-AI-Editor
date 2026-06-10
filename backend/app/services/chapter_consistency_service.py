from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.character import Character
from app.models.plot_line import PlotLine
from app.models.worldbook_entry import WorldbookEntry
from app.services.openrouter_service import generate_with_openrouter
from app.services.writing_constraints_service import build_constraint_block, load_project_constraints


def run_chapter_consistency_check(db: Session, project_id: int, chapter_id: int) -> dict:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise ValueError("Chapter not found in project")

    plan = db.scalar(select(ChapterPlan).where(ChapterPlan.chapter_id == chapter_id))
    if plan is None:
        raise ValueError("Chapter plan not found")

    characters = list(
        db.scalars(select(Character).where(Character.project_id == project_id).order_by(Character.updated_at.desc()).limit(8))
    )
    plot_lines = list(
        db.scalars(select(PlotLine).where(PlotLine.project_id == project_id).order_by(PlotLine.priority.desc()).limit(5))
    )
    worldbook_entries = list(
        db.scalars(
            select(WorldbookEntry).where(WorldbookEntry.project_id == project_id).order_by(WorldbookEntry.updated_at.desc()).limit(5)
        )
    )

    constraints = load_project_constraints(db, project_id)
    constraint_block = build_constraint_block(constraints, include_word_budget=False)

    system_prompt = (
        "你是一位严格的小说一致性审校编辑。请检查章节草稿是否与章节计划、主要角色、"
        "剧情线、世界观规则以及创作约束（题材/风格/基调）保持一致。\n"
        "报告必须包含以下小节：\n"
        "- Consistency Summary（总体结论）\n"
        "- Issues（问题清单）\n"
        "- Suggested Fixes（修复建议）\n"
        "- Scores（评分，必须严格输出这一行格式，分数为 0-100 的整数）：\n"
        "  角色: <分> | 剧情: <分> | 世界: <分> | 节奏: <分> | 风格: <分>\n"
        "评分需客观反映草稿在各维度的达成度，缺陷越多分越低。"
    )
    user_prompt = (
        f"{constraint_block}\n\n"
        f"Chapter title: {chapter.title}\n"
        f"Chapter plan:\n{plan.design_brief}\n\nBeat sheet:\n{plan.beat_sheet}\n\n"
        f"Draft:\n{chapter.draft_content or ''}\n\n"
        "Characters:\n"
        + "\n".join(
            [f"- {item.name}: goal={item.goal or ''}; arc={item.arc_summary or ''}" for item in characters]
        )
        + "\n\nPlot Lines:\n"
        + "\n".join([f"- {item.title}: conflict={item.conflict or ''}" for item in plot_lines])
        + "\n\nWorldbook:\n"
        + "\n".join([f"- {item.title}: {item.content[:180]}" for item in worldbook_entries])
    )

    result = generate_with_openrouter(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        preferred_keywords=["qwen", "mistral", "gemini", "llama"],
        role="controller",
    )
    return {
        "model": result["model"]["id"],
        "report": result["completion"]["choices"][0]["message"]["content"],
    }
