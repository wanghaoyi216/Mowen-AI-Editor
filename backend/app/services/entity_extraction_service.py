from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_task import TaskLog
from app.models.character import Character
from app.models.character_relationship import CharacterRelationship
from app.models.worldbook_entry import WorldbookEntry
from app.schemas.entity_extraction import EntityExtractionRequest
from app.services.graph_service import (
    sync_character_to_neo4j,
    sync_relationship_to_neo4j,
    sync_worldbook_entry_to_neo4j,
)


KNOWN_WORLD_CATEGORIES = {
    "city": "location",
    "location": "location",
    "place": "location",
    "地点": "location",
    "城市": "location",
    "rule": "rule",
    "规则": "rule",
    "item": "item",
    "物品": "item",
    "concept": "concept",
    "概念": "concept",
}


@dataclass
class ExtractedCharacter:
    name: str
    identity: str | None = None
    personality: str | None = None
    motivation: str | None = None


@dataclass
class ExtractedWorldbookEntry:
    title: str
    category: str = "concept"
    content: str = ""


@dataclass
class ExtractedRelationship:
    source: str
    target: str
    relation_type: str = "related"
    intensity: float = 1.0
    note: str | None = None


@dataclass
class ExtractedGraph:
    characters: list[ExtractedCharacter] = field(default_factory=list)
    worldbook_entries: list[ExtractedWorldbookEntry] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value.strip(" ，。、《》:：；;,."))


def _unique_by_name(items: list[Any], attr: str = "name") -> list[Any]:
    seen: set[str] = set()
    result = []
    for item in items:
        value = _clean_name(str(getattr(item, attr)))
        if not value or value in seen:
            continue
        setattr(item, attr, value)
        seen.add(value)
        result.append(item)
    return result


def _extract_from_json_payload(text: str) -> ExtractedGraph | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    graph = ExtractedGraph()
    for item in payload.get("characters", []):
        if isinstance(item, dict) and item.get("name"):
            graph.characters.append(
                ExtractedCharacter(
                    name=str(item["name"]),
                    identity=item.get("identity"),
                    personality=item.get("personality"),
                    motivation=item.get("motivation"),
                )
            )
    for item in payload.get("worldbook_entries", []):
        if isinstance(item, dict) and item.get("title"):
            category = KNOWN_WORLD_CATEGORIES.get(str(item.get("category", "")).lower(), str(item.get("category") or "concept"))
            graph.worldbook_entries.append(
                ExtractedWorldbookEntry(
                    title=str(item["title"]),
                    category=category,
                    content=str(item.get("content") or item.get("summary") or ""),
                )
            )
    for item in payload.get("relationships", []):
        if isinstance(item, dict) and item.get("source") and item.get("target"):
            graph.relationships.append(
                ExtractedRelationship(
                    source=str(item["source"]),
                    target=str(item["target"]),
                    relation_type=str(item.get("relation_type") or item.get("type") or "related"),
                    intensity=float(item.get("intensity") or 1.0),
                    note=item.get("note"),
                )
            )
    return graph


def _deterministic_extract(text: str) -> ExtractedGraph:
    json_graph = _extract_from_json_payload(text)
    if json_graph is not None:
        json_graph.characters = _unique_by_name(json_graph.characters)
        json_graph.worldbook_entries = _unique_by_name(json_graph.worldbook_entries, "title")
        return json_graph

    graph = ExtractedGraph()
    character_patterns = [
        r"(?:角色|人物|主角|配角)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})",
        r"([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})(?:是|为)(?:主角|配角|反派|调查员|领航员|修士|侦探)",
    ]
    for pattern in character_patterns:
        for match in re.finditer(pattern, text):
            graph.characters.append(ExtractedCharacter(name=match.group(1)))

    world_patterns = [
        (r"(?:地点|城市|场景)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,30})", "location"),
        (r"(?:规则|力量体系)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,30})", "rule"),
        (r"(?:物品|道具)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,30})", "item"),
        (r"(?:概念|组织)[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,30})", "concept"),
    ]
    for pattern, category in world_patterns:
        for match in re.finditer(pattern, text):
            title = match.group(1)
            graph.worldbook_entries.append(
                ExtractedWorldbookEntry(title=title, category=category, content=f"从文本中提取的{category}：{title}")
            )

    relationship_patterns = [
        r"([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})\s*(?:与|和)\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})\s*(?:是|形成|建立)?\s*(敌对|同盟|恋爱|师徒|亲属|合作|对立|朋友|盟友)",
        r"关系[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})\s*[-—>]+?\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,24})\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z0-9_·]{2,20})",
    ]
    for pattern in relationship_patterns:
        for match in re.finditer(pattern, text):
            source, target, relation_type = match.group(1), match.group(2), match.group(3)
            graph.relationships.append(
                ExtractedRelationship(source=source, target=target, relation_type=relation_type, intensity=1.0)
            )
            graph.characters.extend([ExtractedCharacter(name=source), ExtractedCharacter(name=target)])

    graph.characters = _unique_by_name(graph.characters)
    graph.worldbook_entries = _unique_by_name(graph.worldbook_entries, "title")
    return graph


def _find_character(db: Session, project_id: int, name: str) -> Character | None:
    return db.scalar(select(Character).where(Character.project_id == project_id, Character.name == name))


def _find_worldbook_entry(db: Session, project_id: int, title: str) -> WorldbookEntry | None:
    return db.scalar(select(WorldbookEntry).where(WorldbookEntry.project_id == project_id, WorldbookEntry.title == title))


def _find_relationship(
    db: Session,
    project_id: int,
    source_character_id: int,
    target_character_id: int,
    relation_type: str,
) -> CharacterRelationship | None:
    return db.scalar(
        select(CharacterRelationship).where(
            CharacterRelationship.project_id == project_id,
            CharacterRelationship.source_character_id == source_character_id,
            CharacterRelationship.target_character_id == target_character_id,
            CharacterRelationship.relation_type == relation_type,
        )
    )


def extract_entities_from_text(db: Session, project_id: int, payload: EntityExtractionRequest) -> dict[str, Any]:
    graph = _deterministic_extract(payload.text)
    added_entities = 0
    updated_entities = 0
    added_relationships = 0
    updated_relationships = 0
    character_map: dict[str, Character] = {}

    for item in graph.characters:
        existing = _find_character(db, project_id, item.name)
        if existing is None:
            existing = Character(
                project_id=project_id,
                name=item.name,
                identity=item.identity,
                personality=item.personality,
                motivation=item.motivation,
                status="active",
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
            added_entities += 1
        else:
            changed = False
            for field_name in ("identity", "personality", "motivation"):
                value = getattr(item, field_name)
                if value and not getattr(existing, field_name):
                    setattr(existing, field_name, value)
                    changed = True
            if changed:
                db.add(existing)
                db.commit()
                db.refresh(existing)
                updated_entities += 1
        sync_character_to_neo4j(existing)
        character_map[item.name] = existing

    for item in graph.worldbook_entries:
        existing_entry = _find_worldbook_entry(db, project_id, item.title)
        content = item.content or f"从 {payload.source_type} 提取：{item.title}"
        if existing_entry is None:
            existing_entry = WorldbookEntry(
                project_id=project_id,
                title=item.title,
                category=item.category,
                content=content,
                source_type=payload.source_type,
                source_ref=payload.source_ref,
            )
            db.add(existing_entry)
            db.commit()
            db.refresh(existing_entry)
            added_entities += 1
        else:
            if content and content not in existing_entry.content:
                existing_entry.content = f"{existing_entry.content}\n\n{content}"
                db.add(existing_entry)
                db.commit()
                db.refresh(existing_entry)
                updated_entities += 1
        sync_worldbook_entry_to_neo4j(existing_entry)

    for item in graph.relationships:
        source = character_map.get(_clean_name(item.source)) or _find_character(db, project_id, _clean_name(item.source))
        target = character_map.get(_clean_name(item.target)) or _find_character(db, project_id, _clean_name(item.target))
        if source is None or target is None or source.id == target.id:
            continue
        existing_rel = _find_relationship(db, project_id, source.id, target.id, item.relation_type)
        if existing_rel is None:
            existing_rel = CharacterRelationship(
                project_id=project_id,
                source_character_id=source.id,
                target_character_id=target.id,
                relation_type=item.relation_type,
                intensity=item.intensity,
                status="active",
                note=item.note,
            )
            db.add(existing_rel)
            db.commit()
            db.refresh(existing_rel)
            added_relationships += 1
        else:
            changed = False
            if item.intensity and item.intensity != existing_rel.intensity:
                existing_rel.intensity = item.intensity
                changed = True
            if item.note and item.note != existing_rel.note:
                existing_rel.note = item.note
                changed = True
            if changed:
                db.add(existing_rel)
                db.commit()
                db.refresh(existing_rel)
                updated_relationships += 1
        sync_relationship_to_neo4j(db, project_id, existing_rel)

    summary = {
        "added_entities": added_entities,
        "updated_entities": updated_entities,
        "added_relationships": added_relationships,
        "updated_relationships": updated_relationships,
        "characters": [item.name for item in graph.characters],
        "worldbook_entries": [item.title for item in graph.worldbook_entries],
        "relationships": [f"{item.source}->{item.target}:{item.relation_type}" for item in graph.relationships],
    }

    if payload.task_id is not None:
        db.add(
            TaskLog(
                task_id=payload.task_id,
                log_type="graph_mutation",
                message="AI analyzed text before graph store",
                payload=json.dumps(summary, ensure_ascii=False),
            )
        )
        db.commit()

    return summary

