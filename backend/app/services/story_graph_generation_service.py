from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.character_event_participation import CharacterEventParticipation
from app.models.character_relationship import CharacterRelationship
from app.models.plot_line import PlotLine
from app.models.story_arc import StoryArc
from app.models.story_event import StoryEvent
from app.models.story_theme import StoryTheme
from app.models.worldbook_entry import WorldbookEntry
from app.services.graph_service import (
    sync_character_to_neo4j,
    sync_relationship_to_neo4j,
    sync_story_arc_to_neo4j,
    sync_story_theme_to_neo4j,
    sync_worldbook_entry_to_neo4j,
)
from app.services.openrouter_service import generate_with_openrouter_fallback

logger = logging.getLogger(__name__)


def _load_project_assets(db: Session, project_id: int) -> dict[str, Any]:
    """加载项目所有资产用于 AI 分析"""
    characters = list(
        db.scalars(
            select(Character)
            .where(Character.project_id == project_id)
            .order_by(Character.updated_at.desc())
            .limit(20)
        )
    )
    plot_lines = list(
        db.scalars(
            select(PlotLine)
            .where(PlotLine.project_id == project_id)
            .order_by(PlotLine.priority.desc())
            .limit(10)
        )
    )
    worldbook = list(
        db.scalars(
            select(WorldbookEntry)
            .where(WorldbookEntry.project_id == project_id)
            .order_by(WorldbookEntry.updated_at.desc())
            .limit(15)
        )
    )
    return {
        "characters": characters,
        "plot_lines": plot_lines,
        "worldbook": worldbook,
    }


def _build_ai_analysis_prompt(assets: dict[str, Any]) -> str:
    """构建 AI 分析提示词，要求输出规范化 JSON 故事脉络"""
    chars_text = "\n".join(
        f"- 角色: {c.name}\n"
        f"  身份: {c.identity or '未知'}\n"
        f"  性格: {c.personality or '未知'}\n"
        f"  目标: {c.goal or '未知'}\n"
        f"  动机: {c.motivation or '未知'}\n"
        f"  弧光: {c.arc_summary or '未知'}"
        for c in assets["characters"]
    )
    plots_text = "\n".join(
        f"- 剧情线: {p.title}\n"
        f"  类型: {p.plot_type or '未知'}\n"
        f"  冲突: {p.conflict or '未知'}\n"
        f"  目标: {p.goal or '未知'}\n"
        f"  赌注: {p.stakes or '未知'}\n"
        f"  摘要: {(p.summary or '')[:200]}"
        for p in assets["plot_lines"]
    )
    world_text = "\n".join(
        f"- 设定: {w.title}\n"
        f"  类别: {w.category or '未知'}\n"
        f"  内容: {(w.content or '')[:300]}"
        for w in assets["worldbook"]
    )

    return (
        "You are a professional novel story architect. Given the following assets (characters, plot lines, world settings), "
        "analyze them and produce a normalized story graph in JSON format.\n\n"
        "You MUST output ONLY valid JSON, no markdown, no explanation.\n\n"
        "The JSON must follow this exact schema:\n"
        "{\n"
        '  "characters": [\n'
        "    {\n"
        '      "name": "角色姓名",\n'
        '      "role_type": "protagonist|antagonist|supporting|mentor|foil|etc",\n'
        '      "identity": "身份描述",\n'
        '      "personality": "性格特征",\n'
        '      "background": "背景故事",\n'
        '      "goal": "角色目标",\n'
        '      "arc_type": "positive|negative|flat|disillusionment"\n'
        "    }\n"
        "  ],\n"
        '  "character_relationships": [\n'
        "    {\n"
        '      "source": "源角色名",\n'
        '      "target": "目标角色名",\n'
        '      "relation_type": "alliance|rivalry|romance|mentorship|family|betrayal|friendship|conflict|love_hate|hierarchy",\n'
        '      "intensity": 0.0-1.0,\n'
        '      "note": "关系描述"\n'
        "    }\n"
        "  ],\n"
        '  "story_arcs": [\n'
        "    {\n"
        '      "title": "故事弧线名称",\n'
        '      "arc_type": "main_plot|subplot|character_arc|theme_arc",\n'
        '      "description": "弧线描述",\n'
        '      "key_beats": ["节拍1", "节拍2", "节拍3"],\n'
        '      "resolution": "弧线结局"\n'
        "    }\n"
        "  ],\n"
        '  "key_events": [\n'
        "    {\n"
        '      "title": "事件名称",\n'
        '      "event_type": "inciting_incident|plot_turnpoint|midpoint|crisis|climax|resolution",\n'
        '      "description": "事件描述",\n'
        '      "participants": ["参与角色名1", "参与角色名2"],\n'
        '      "impact": "high|medium|low",\n'
        '      "related_arc": "关联的故事弧线名称"\n'
        "    }\n"
        "  ],\n"
        '  "theme_connections": [\n'
        "    {\n"
        '      "theme": "主题名称",\n'
        '      "description": "主题描述",\n'
        '      "represented_by": ["角色名1", "角色名2"],\n'
        '      "arc_connection": "关联的故事弧线"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"ASSETS TO ANALYZE:\n\n"
        f"## CHARACTERS:\n{chars_text}\n\n"
        f"## PLOT LINES:\n{plots_text}\n\n"
        f"## WORLD SETTINGS:\n{world_text}\n\n"
        "Analyze the relationships between characters, the story arcs implied by the plot lines, "
        "the key events that drive the narrative, and the thematic connections. "
        "Produce a complete, normalized story graph in the exact JSON format specified above."
    )


def _parse_ai_response(response_text: str) -> dict[str, Any] | None:
    """解析 AI 返回的 JSON 响应（鲁棒版：兼容 markdown 包裹 / 思考残留 / 前后缀文本）。"""
    import re

    text = (response_text or "").strip()
    # 去除 reasoning 残留
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Remove markdown code blocks if present
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 取首 { 到末 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    logger.error("Failed to parse AI story graph response: %s", text[:200])
    return None


def generate_normalized_story_graph(
    db: Session,
    project_id: int,
    task_id: int | None = None,
) -> dict[str, Any]:
    """
    AI 驱动的故事脉络规范化生成服务。

    分析项目中的所有资产（角色、剧情线、世界观），通过 AI 生成规范化的故事脉络图，
    包括人物关系图、情节脉络图、事件网络、主题连接。

    ``task_id`` 可选：传入后会向 AgentEventBus 发送 tool_call / tool_result 事件，
    让前端 Agent 对话窗口实时展示"知识图谱构建"过程。
    """
    assets = _load_project_assets(db, project_id)

    if not assets["characters"] and not assets["plot_lines"]:
        logger.warning("No assets found for project %d, skipping story graph generation", project_id)
        return {"status": "skipped", "reason": "no assets"}

    prompt = _build_ai_analysis_prompt(assets)

    logger.info("Calling AI to generate normalized story graph for project %d", project_id)

    _emit_graph_event(
        task_id, "tool_call", tool="build_knowledge_graph",
        characters=len(assets["characters"]), plot_lines=len(assets["plot_lines"]),
    )

    result = generate_with_openrouter_fallback(
        system_prompt=(
            "You are a professional novel story architect. "
            "Your job is to analyze novel assets and produce a normalized, structured story graph in JSON format. "
            "Follow the exact schema provided. Output ONLY valid JSON."
        ),
        user_prompt=prompt,
        max_model_attempts=3,
        role="controller",
    )

    completion_text = result["completion"]["choices"][0]["message"]["content"]
    graph_data = _parse_ai_response(completion_text)
    
    if graph_data is None:
        logger.error("AI returned invalid JSON for story graph generation")
        _emit_graph_event(task_id, "tool_result", tool="build_knowledge_graph", status="failed", error="invalid_json")
        return {"status": "failed", "reason": "invalid_json", "model": result.get("model")}

    # Store and sync to Neo4j
    summary = _store_and_sync_story_graph(db, project_id, graph_data)
    summary["model"] = result.get("model")
    summary["status"] = "completed"
    _emit_graph_event(
        task_id, "tool_result", tool="build_knowledge_graph", status="success",
        relationships=summary.get("added_relationships", 0),
        events=summary.get("added_events", 0),
        arcs=summary.get("added_arcs", 0),
        themes=summary.get("added_themes", 0),
    )
    return summary


def _emit_graph_event(task_id: int | None, event_type: str, **data: Any) -> None:
    """向 AgentEventBus 发布知识图谱构建事件（task_id 缺失时静默跳过）。"""
    if not task_id:
        return
    try:
        from app.services.agent_event_bus import AgentEvent, bus

        bus.publish(
            AgentEvent(event_type=event_type, task_id=task_id, phase="graph", data=data)
        )
    except Exception as exc:  # noqa: BLE001 - 事件发布失败不影响图谱生成
        logger.debug("graph event publish failed: %s", exc)


def _store_and_sync_story_graph(db: Session, project_id: int, graph_data: dict[str, Any]) -> dict[str, Any]:
    """将 AI 生成的故事脉络存储到 PostgreSQL 并同步到 Neo4j"""
    added_relationships = 0
    updated_relationships = 0
    added_arcs = 0
    added_events = 0
    added_themes = 0
    
    # Build character name -> ID map（同时记录每个角色的 book_id，供关系继承）
    char_name_to_id: dict[str, int] = {}
    char_id_to_book: dict[int, int | None] = {}
    existing_chars = list(db.scalars(select(Character).where(Character.project_id == project_id)))
    for c in existing_chars:
        char_name_to_id[c.name] = c.id
        char_id_to_book[c.id] = getattr(c, "book_id", None)
    # 默认 book：取任一已有角色的 book_id，保证新建关系/占位角色落在同一本书内，
    # 否则在"按书筛选"的知识图谱视图下会被过滤掉。
    default_book_id = next((b for b in char_id_to_book.values() if b is not None), None)

    # 1. Process character relationships
    for rel in graph_data.get("character_relationships", []):
        source_name = rel.get("source", "").strip()
        target_name = rel.get("target", "").strip()
        if not source_name or not target_name:
            continue
        
        source_id = char_name_to_id.get(source_name)
        target_id = char_name_to_id.get(target_name)
        
        if source_id is None or target_id is None:
            # Create placeholder characters if needed
            for name, role_hint in [(source_name, "character"), (target_name, "character")]:
                if name not in char_name_to_id:
                    new_char = Character(
                        project_id=project_id,
                        name=name,
                        identity="AI 故事脉络分析生成",
                        role_type="story_generated",
                        status="active",
                        book_id=default_book_id,
                    )
                    db.add(new_char)
                    db.commit()
                    db.refresh(new_char)
                    char_name_to_id[name] = new_char.id
                    char_id_to_book[new_char.id] = new_char.book_id
                    sync_character_to_neo4j(new_char)
            
            source_id = char_name_to_id.get(source_name)
            target_id = char_name_to_id.get(target_name)
            if source_id is None or target_id is None:
                continue
        
        if source_id == target_id:
            continue
        
        # Check if relationship already exists
        from app.models.character_relationship import CharacterRelationship as CR
        existing = db.scalar(
            select(CR).where(
                CR.project_id == project_id,
                CR.source_character_id == source_id,
                CR.target_character_id == target_id,
                CR.relation_type == rel.get("relation_type", "related"),
            )
        )
        
        if existing is None:
            rel_book_id = char_id_to_book.get(source_id) or char_id_to_book.get(target_id) or default_book_id
            new_rel = CharacterRelationship(
                project_id=project_id,
                source_character_id=source_id,
                target_character_id=target_id,
                relation_type=rel.get("relation_type", "related"),
                intensity=rel.get("intensity", 0.5),
                status="active",
                note=rel.get("note", ""),
                book_id=rel_book_id,
            )
            db.add(new_rel)
            db.commit()
            db.refresh(new_rel)
            sync_relationship_to_neo4j(db, project_id, new_rel)
            added_relationships += 1
        else:
            changed = False
            if rel.get("intensity") and rel["intensity"] != existing.intensity:
                existing.intensity = rel["intensity"]
                changed = True
            if rel.get("note") and rel["note"] != existing.note:
                existing.note = rel["note"]
                changed = True
            if changed:
                db.add(existing)
                db.commit()
                sync_relationship_to_neo4j(db, project_id, existing)
                updated_relationships += 1
    
    # 2. Process story arcs —— 写新表 StoryArc（不再滥用 PlotLine）。
    arc_type_map = {
        "main_plot": "overarching",
        "subplot": "subplot",
        "character_arc": "character_arc",
        "theme_arc": "theme_arc",
    }
    for arc in graph_data.get("story_arcs", []):
        arc_title = arc.get("title", "").strip()
        if not arc_title:
            continue

        existing_arc = db.scalar(
            select(StoryArc).where(
                StoryArc.project_id == project_id,
                StoryArc.title == arc_title,
            )
        )

        if existing_arc is None:
            beats = arc.get("key_beats", []) or []
            start_beat = beats[0] if len(beats) > 0 else ""
            climax_beat = beats[len(beats) // 2] if len(beats) > 0 else ""
            resolution_beat = beats[-1] if len(beats) > 0 else arc.get("resolution", "")
            new_arc = StoryArc(
                project_id=project_id,
                book_id=default_book_id,
                title=arc_title,
                arc_type=arc_type_map.get(str(arc.get("arc_type", "main_plot")).lower(), "overarching"),
                description=arc.get("description", ""),
                start_beat=start_beat,
                climax_beat=climax_beat,
                resolution_beat=resolution_beat or arc.get("resolution", ""),
                status="mapped",
                priority=3,
                source_type="ai_story_graph",
                source_ref="story_graph_generation",
            )
            db.add(new_arc)
            db.commit()
            db.refresh(new_arc)
            sync_story_arc_to_neo4j(new_arc)
            added_arcs += 1
    
    # 3. Process key events —— 写真正的 StoryEvent 表，不再向 WorldbookEntry
    #    写 category='story_event' 的假条目（避免"世界观"视图混入事件节点）。
    for event in graph_data.get("key_events", []):
        event_title = event.get("title", "").strip()
        if not event_title:
            continue

        participants = event.get("participants", []) or []
        impact_map = {"high": 3, "medium": 2, "low": 1}
        existing_story_event = db.scalar(
            select(StoryEvent).where(
                StoryEvent.project_id == project_id,
                StoryEvent.title == event_title,
            )
        )
        if existing_story_event is None:
            story_event = StoryEvent(
                project_id=project_id,
                book_id=default_book_id,
                title=event_title,
                event_type=event.get("event_type", "scene") or "scene",
                summary=event.get("description", ""),
                expected_outcome=event.get("related_arc", ""),
                impact_level=impact_map.get(str(event.get("impact", "medium")).lower(), 2),
                status="planned",
                source_type="ai_story_graph",
            )
            db.add(story_event)
            db.commit()
            db.refresh(story_event)
            from app.services.graph_service import sync_story_event_to_neo4j
            sync_story_event_to_neo4j(story_event)
            added_events += 1
            # 写入角色—事件参与边
            for participant_name in participants:
                pname = str(participant_name).strip()
                pid = char_name_to_id.get(pname)
                if pid is None:
                    continue
                existing_p = db.scalar(
                    select(CharacterEventParticipation).where(
                        CharacterEventParticipation.character_id == pid,
                        CharacterEventParticipation.event_id == story_event.id,
                    )
                )
                if existing_p is not None:
                    continue
                participation = CharacterEventParticipation(
                    project_id=project_id,
                    book_id=char_id_to_book.get(pid) or default_book_id,
                    character_id=pid,
                    event_id=story_event.id,
                    role_type="participant",
                    impact_score=float(impact_map.get(str(event.get("impact", "medium")).lower(), 2)),
                    note=event.get("description", "")[:200] if event.get("description") else None,
                )
                db.add(participation)
            db.commit()
    
    # 4. Process theme connections —— 写新表 StoryTheme（不再滥用 WorldbookEntry）。
    for theme in graph_data.get("theme_connections", []):
        theme_name = theme.get("theme", "").strip()
        if not theme_name:
            continue

        existing_theme = db.scalar(
            select(StoryTheme).where(
                StoryTheme.project_id == project_id,
                StoryTheme.name == theme_name,
            )
        )

        if existing_theme is None:
            represented = theme.get("represented_by", []) or []
            new_theme = StoryTheme(
                project_id=project_id,
                book_id=default_book_id,
                name=theme_name,
                description=theme.get("description", ""),
                represented_by=json.dumps(list(represented), ensure_ascii=False),
                arc_connection=theme.get("arc_connection", ""),
                source_type="ai_story_graph",
            )
            db.add(new_theme)
            db.commit()
            db.refresh(new_theme)
            sync_story_theme_to_neo4j(new_theme)
            added_themes += 1

    return {
        "added_relationships": added_relationships,
        "updated_relationships": updated_relationships,
        "added_arcs": added_arcs,
        "added_events": added_events,
        "added_themes": added_themes,
        "total_characters": len(char_name_to_id),
    }
