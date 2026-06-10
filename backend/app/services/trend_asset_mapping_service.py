import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.plot_line import PlotLine
from app.models.trend_exploration import TrendExploration
from app.models.worldbook_entry import WorldbookEntry
from app.schemas.character import CharacterCreate
from app.schemas.plot_line import PlotLineCreate
from app.schemas.worldbook_entry import WorldbookEntryCreate
from app.services.character_service import create_character
from app.services.plot_service import create_plot_line
from app.services.worldbook_service import create_worldbook_entry


def _load_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _as_text(item: object, *keys: str) -> str:
    if isinstance(item, dict):
        for key in keys:
            value = item.get(key)
            if value:
                return str(value).strip()
        return ""
    return str(item).strip()


def _existing_trend_assets(db: Session, project_id: int, trend_id: int) -> tuple[list[PlotLine], list[Character], list[WorldbookEntry]]:
    source_ref = f"trend:{trend_id}"
    plot_lines = list(
        db.scalars(
            select(PlotLine).where(
                PlotLine.project_id == project_id,
                PlotLine.plot_type == "trend_generated",
                PlotLine.start_phase == source_ref,
            )
        )
    )
    characters = list(
        db.scalars(
            select(Character).where(
                Character.project_id == project_id,
                Character.role_type == "trend_candidate",
                Character.alias == source_ref,
            )
        )
    )
    worldbook_entries = list(
        db.scalars(
            select(WorldbookEntry).where(
                WorldbookEntry.project_id == project_id,
                WorldbookEntry.source_type == "trend_exploration",
                WorldbookEntry.source_ref == str(trend_id),
            )
        )
    )
    return plot_lines, characters, worldbook_entries


def map_trend_to_assets(
    db: Session,
    project_id: int,
    trend_id: int,
    create_plot_lines: bool = True,
    create_character_candidates: bool = True,
    create_worldbook_entries: bool = True,
) -> dict:
    trend = db.get(TrendExploration, trend_id)
    if trend is None:
        raise ValueError("Trend exploration not found")
    if trend.project_id != project_id:
        raise ValueError("Trend exploration does not belong to this project")

    topics = _load_json_list(trend.extracted_topics)
    tags = _load_json_list(trend.extracted_tags)
    directions = _load_json_list(trend.suggested_directions)
    existing_plot_lines, existing_characters, existing_worldbook_entries = _existing_trend_assets(db, project_id, trend_id)

    created_plot_lines = list(existing_plot_lines)
    created_characters = list(existing_characters)
    created_worldbook_entries = list(existing_worldbook_entries)
    source_ref = f"trend:{trend_id}"

    if create_plot_lines and not existing_plot_lines:
        for direction in directions[:3]:
            direction_title = _as_text(direction, "title", "premise")[:100] or "趋势生成剧情线"
            premise = _as_text(direction, "premise", "title") or "根据热点趋势生成的剧情假设"
            conflict = _as_text(direction, "conflict") or "根据热点题材提炼核心冲突"
            created_plot_lines.append(
                create_plot_line(
                    db,
                    project_id,
                    PlotLineCreate(
                        title=direction_title,
                        plot_type="trend_generated",
                        summary=premise,
                        goal=f"围绕趋势主题展开故事线：{direction_title}",
                        conflict=conflict,
                        stakes="验证该题材方向是否适合当前小说项目",
                        start_phase=source_ref,
                        end_phase="待人工筛选",
                        status="mapped",
                        priority=5,
                    ),
                )
            )

    if create_character_candidates and not existing_characters:
        for topic in topics[:3]:
            topic_title = _as_text(topic, "title", "insight")[:60] or "趋势角色候选"
            insight = _as_text(topic, "insight", "title") or "由热点探索生成的角色候选"
            created_characters.append(
                create_character(
                    db,
                    project_id,
                    CharacterCreate(
                        name=f"{topic_title[:24]}角色候选",
                        alias=source_ref,
                        role_type="trend_candidate",
                        identity="由热点探索生成的角色候选",
                        personality=f"受趋势洞察“{topic_title}”启发形成的个性轮廓",
                        motivation="服务于趋势主题与叙事冲突",
                        goal="待人工或后续 AI 进一步细化",
                        status="active",
                        arc_summary=f"角色候选来源于趋势洞察：{insight}",
                    ),
                )
            )

    if create_worldbook_entries and not existing_worldbook_entries:
        for topic in topics[:3]:
            topic_title = _as_text(topic, "title", "insight")[:80] or "趋势设定条目"
            insight = _as_text(topic, "insight", "title") or "待补充"
            first_direction = _as_text(directions[0], "title", "premise") if directions else "待补充"
            created_worldbook_entries.append(
                create_worldbook_entry(
                    db,
                    project_id,
                    WorldbookEntryCreate(
                        title=f"{topic_title[:48]} 设定条目",
                        category="trend_insight",
                        content=(
                            f"趋势洞察：{insight}\n"
                            f"参考标签：{', '.join(tags[:8])}\n"
                            f"建议方向：{first_direction}"
                        ),
                        source_type="trend_exploration",
                        source_ref=str(trend.id),
                    ),
                )
            )

    return {
        "trend": trend,
        "plot_lines": created_plot_lines,
        "characters": created_characters,
        "worldbook_entries": created_worldbook_entries,
    }
