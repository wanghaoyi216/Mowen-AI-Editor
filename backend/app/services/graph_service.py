from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.graph.client import build_neo4j_client
from app.models.ai_task import AITask, TaskStep
from app.models.chapter import Chapter
from app.models.chapter_plan import ChapterPlan
from app.models.character import Character
from app.models.character_event_participation import CharacterEventParticipation
from app.models.character_relationship import CharacterRelationship
from app.models.plot_line import PlotLine
from app.models.story_arc import StoryArc
from app.models.story_event import StoryEvent
from app.models.story_theme import StoryTheme
from app.models.worldbook_entry import WorldbookEntry
from app.schemas.graph import CharacterRelationshipCreate


# ==== Graph Type 严格分流 ==================================================
# 每个 graph_type 独立决定"包含哪些节点/边"，互不串台：
#   story_entity      -> Character + PlotLine + StoryEvent + Chapter + ChapterPlan + WorldbookEntry
#   character         -> Character + RELATED_TO
#   plot / plot_line  -> PlotLine(plot_type in (plot_line, subplot, chapter_scene, main_plot))
#                        排除 plot_type='story_arc' / 'trend_generated'
#   event / event_network -> StoryEvent + Character-PARTICIPATES_IN
#   chapter / chapter_structure -> Chapter + ChapterPlan + (PRECEDES / HAS_PLAN)
#   worldbook / worldview -> WorldbookEntry (category='worldbook' OR NULL)
#   story_arc / arc   -> StoryArc + StoryTheme + 涉及的 Chapter / Character
#   task_workflow     -> AITask + TaskStep
STORY_ENTITY_GRAPH_TYPES = {"story_entity", "character", "plot", "event"}
CHAPTER_GRAPH_TYPES = {"chapter_structure", "chapter", "chapter_plan"}
STORY_ARC_GRAPH_TYPES = {"story_arc", "arc"}
PLOT_REAL_PLOT_TYPES = ("plot_line", "subplot", "chapter_scene", "main_plot", None)
WORLDBOOK_CATEGORIES = ("worldbook",)  # 不包含 'story_event' / 'theme'


def _normalize_graph_type(graph_type: str | None) -> str:
    normalized = (graph_type or "story_entity").strip().lower()
    aliases = {
        "mixed": "story_entity",
        "entity": "story_entity",
        "entities": "story_entity",
        "character_relationship": "story_entity",
        "task": "task_workflow",
        "workflow": "task_workflow",
        "chapter_graph": "chapter_structure",
        "plot_line": "plot",
        "chapter_plan": "chapter_structure",
    }
    return aliases.get(normalized, normalized)


def _get_task_workflow_graph(db: Session, project_id: int) -> dict:
    nodes: list[dict] = []
    relationships: list[dict] = []
    tasks = list(db.scalars(select(AITask).where(AITask.project_id == project_id).order_by(AITask.created_at.desc())))
    task_ids = [task.id for task in tasks]
    steps = (
        list(
            db.scalars(
                select(TaskStep)
                .where(TaskStep.task_id.in_(task_ids))
                .order_by(TaskStep.task_id.desc(), TaskStep.step_no.asc())
            )
        )
        if task_ids
        else []
    )

    for task in tasks:
        nodes.append(
            {
                "id": f"task-{task.id}",
                "entity_id": task.id,
                "label": task.title,
                "type": "task",
                "meta": {
                    "status": task.status,
                    "task_type": task.task_type,
                    "module_type": task.module_type,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "finished_at": task.finished_at.isoformat() if task.finished_at else None,
                },
            }
        )

    previous_step_by_task: dict[int, TaskStep] = {}
    for step in steps:
        nodes.append(
            {
                "id": f"task-step-{step.id}",
                "entity_id": step.id,
                "label": f"{step.step_no}. {step.step_name}",
                "type": "task_step",
                "meta": {
                    "status": step.status,
                    "step_type": step.step_type,
                    "react_state": step.react_state,
                    "tool_name": step.tool_name,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "finished_at": step.finished_at.isoformat() if step.finished_at else None,
                },
            }
        )
        relationships.append(
            {
                "id": f"task-{step.task_id}-step-{step.id}",
                "source": f"task-{step.task_id}",
                "target": f"task-step-{step.id}",
                "type": "has_step",
                "meta": {},
            }
        )
        previous = previous_step_by_task.get(step.task_id)
        if previous is not None:
            relationships.append(
                {
                    "id": f"task-step-{previous.id}-next-{step.id}",
                    "source": f"task-step-{previous.id}",
                    "target": f"task-step-{step.id}",
                    "type": "next_step",
                    "meta": {},
                }
            )
        previous_step_by_task[step.task_id] = step

    return {"source": "task-runtime", "nodes": nodes, "relationships": relationships}


def create_character_relationship(
    db: Session,
    project_id: int,
    payload: CharacterRelationshipCreate,
) -> CharacterRelationship:
    if payload.source_character_id == payload.target_character_id:
        raise ValueError("Source and target characters must be different")

    source = db.get(Character, payload.source_character_id)
    target = db.get(Character, payload.target_character_id)
    if source is None or target is None:
        raise ValueError("Characters not found")
    if source.project_id != project_id or target.project_id != project_id:
        raise ValueError("Characters must belong to the same project")
    if source.book_id is not None and target.book_id is not None and source.book_id != target.book_id:
        raise ValueError("Characters must belong to the same book")

    data = payload.model_dump()
    data["book_id"] = data.get("book_id") or source.book_id or target.book_id
    relationship = CharacterRelationship(project_id=project_id, **data)
    db.add(relationship)
    db.commit()
    db.refresh(relationship)

    sync_relationship_to_neo4j(db, project_id, relationship)
    return relationship


def sync_character_to_neo4j(character: Character) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_character(
            {
                "project_id": character.project_id,
                "book_id": character.book_id,
                "character_id": character.id,
                "name": character.name,
                "alias": character.alias,
                "role_type": character.role_type,
                "status": character.status,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_plot_line_to_neo4j(plot_line: PlotLine) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_plot_line(
            {
                "project_id": plot_line.project_id,
                "book_id": plot_line.book_id,
                "plot_line_id": plot_line.id,
                "chapter_id": plot_line.chapter_id,
                "title": plot_line.title,
                "plot_type": plot_line.plot_type,
                "status": plot_line.status,
                "priority": plot_line.priority,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_chapter_to_neo4j(chapter: Chapter) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_chapter(
            {
                "project_id": chapter.project_id,
                "book_id": chapter.book_id,
                "chapter_id": chapter.id,
                "title": chapter.title,
                "chapter_no": chapter.chapter_no,
                "status": chapter.status,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_story_event_to_neo4j(story_event: StoryEvent) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_story_event(
            {
                "project_id": story_event.project_id,
                "book_id": story_event.book_id,
                "event_id": story_event.id,
                "plot_line_id": story_event.plot_line_id,
                "chapter_id": story_event.chapter_id,
                "title": story_event.title,
                "event_type": story_event.event_type,
                "status": story_event.status,
                "impact_level": story_event.impact_level,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_chapter_plan_to_neo4j(chapter_plan: ChapterPlan) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_chapter_plan(
            {
                "project_id": chapter_plan.project_id,
                "book_id": chapter_plan.book_id,
                "chapter_plan_id": chapter_plan.id,
                "chapter_id": chapter_plan.chapter_id,
                "plot_line_id": chapter_plan.plot_line_id,
                "title": chapter_plan.title,
                "status": chapter_plan.status,
                "selected_model": chapter_plan.selected_model,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_character_event_participation_to_neo4j(participation: CharacterEventParticipation) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_character_event_participation(
            {
                "project_id": participation.project_id,
                "book_id": participation.book_id,
                "character_id": participation.character_id,
                "event_id": participation.event_id,
                "role_type": participation.role_type,
                "impact_score": participation.impact_score,
                "note": participation.note,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_worldbook_entry_to_neo4j(entry: WorldbookEntry) -> bool:
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_worldbook_entry(
            {
                "project_id": entry.project_id,
                "book_id": entry.book_id,
                "worldbook_entry_id": entry.id,
                "title": entry.title,
                "category": entry.category,
                "content": entry.content,
                "source_type": entry.source_type,
                "source_ref": entry.source_ref,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_story_arc_to_neo4j(arc: StoryArc) -> bool:
    """把 StoryArc 节点同步到 Neo4j —— ``故事脉络``视图的真实数据源。"""
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_story_arc(
            {
                "project_id": arc.project_id,
                "book_id": arc.book_id,
                "story_arc_id": arc.id,
                "title": arc.title,
                "arc_type": arc.arc_type,
                "description": arc.description,
                "start_beat": arc.start_beat,
                "climax_beat": arc.climax_beat,
                "resolution_beat": arc.resolution_beat,
                "status": arc.status,
                "priority": arc.priority,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_story_theme_to_neo4j(theme: StoryTheme) -> bool:
    """把 StoryTheme 节点同步到 Neo4j。"""
    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_story_theme(
            {
                "project_id": theme.project_id,
                "book_id": theme.book_id,
                "story_theme_id": theme.id,
                "name": theme.name,
                "description": theme.description,
                "represented_by": theme.represented_by,
                "arc_connection": theme.arc_connection,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def sync_relationship_to_neo4j(db: Session, project_id: int, relationship: CharacterRelationship) -> bool:
    source = db.get(Character, relationship.source_character_id)
    target = db.get(Character, relationship.target_character_id)
    if source is None or target is None:
        return False

    client = build_neo4j_client()
    try:
        if not client.is_available():
            return False
        client.upsert_character(
            {
                "project_id": source.project_id,
                "book_id": source.book_id,
                "character_id": source.id,
                "name": source.name,
                "alias": source.alias,
                "role_type": source.role_type,
                "status": source.status,
            }
        )
        client.upsert_character(
            {
                "project_id": target.project_id,
                "book_id": target.book_id,
                "character_id": target.id,
                "name": target.name,
                "alias": target.alias,
                "role_type": target.role_type,
                "status": target.status,
            }
        )
        client.upsert_relationship(
            {
                "project_id": project_id,
                "book_id": relationship.book_id,
                "source_character_id": source.id,
                "target_character_id": target.id,
                "source_name": source.name,
                "target_name": target.name,
                "relation_type": relationship.relation_type,
                "intensity": relationship.intensity,
                "status": relationship.status,
                "note": relationship.note,
            }
        )
        return True
    except Exception:
        return False
    finally:
        client.close()


def get_project_graph(
    db: Session,
    project_id: int,
    character_id: int | None = None,
    chapter_id: int | None = None,
    graph_type: str = "story_entity",
    book_id: int | None = None,
) -> dict:
    """查询项目知识图谱。

    参数：
        project_id:    项目主键
        character_id:  限定只显示与某角色相关的边
        chapter_id:    限定只显示与某章节相关的事件/plan
        graph_type:    ``story_entity`` / ``character`` / ``plot`` / ``event`` /
                       ``chapter_structure`` / ``chapter`` / ``story_arc`` /
                       ``arc`` / ``event_network`` / ``worldview`` / ``worldbook`` /
                       ``task_workflow``
        book_id:       按书隔离

    重构要点（修旧 bug）：
      * ``plot`` 视图**排除** ``plot_type='story_arc'`` / ``'trend_generated'``，不再混入故事弧
      * ``worldbook`` 视图**只读** ``category='worldbook'`` / NULL，不再混入事件与主题
      * ``story_arc`` 视图走新的 ``StoryArc`` + ``StoryTheme`` 表，不再从 PlotLine / Worldbook 借数据
      * ``character`` 视图**不混** PlotLine / StoryEvent 等非人物节点
    """
    graph_type = _normalize_graph_type(graph_type)
    if graph_type == "task_workflow":
        return _get_task_workflow_graph(db, project_id)

    nodes: list[dict] = []
    edges: list[dict] = []

    # ----------------------------------------------------------------------
    # branch 1: story_arc / arc —— 走新 StoryArc + StoryTheme 表
    # ----------------------------------------------------------------------
    if graph_type in STORY_ARC_GRAPH_TYPES:
        return _get_story_arc_subgraph(db, project_id, book_id)

    # ----------------------------------------------------------------------
    # branch 2: character —— 严格只显示 Character 节点 + RELATED_TO 边
    # ----------------------------------------------------------------------
    if graph_type == "character":
        return _get_character_subgraph(db, project_id, character_id, book_id, chapter_id)

    # ----------------------------------------------------------------------
    # branch 3: worldbook / worldview —— 严格只读 worldview 类条目
    # ----------------------------------------------------------------------
    if graph_type in ("worldbook", "worldview"):
        return _get_worldbook_subgraph(db, project_id, book_id)

    # ----------------------------------------------------------------------
    # branch 4: chapter / chapter_structure / chapter_plan
    # ----------------------------------------------------------------------
    if graph_type in CHAPTER_GRAPH_TYPES:
        return _get_chapter_subgraph(db, project_id, chapter_id, book_id)

    # ----------------------------------------------------------------------
    # branch 5: plot / plot_line —— 严格排除 story_arc / trend_generated
    # ----------------------------------------------------------------------
    if graph_type in ("plot", "plot_line"):
        return _get_plot_subgraph(db, project_id, chapter_id, book_id)

    # ----------------------------------------------------------------------
    # branch 6: event / event_network —— 严格只读 StoryEvent + 参与边
    # ----------------------------------------------------------------------
    if graph_type in ("event", "event_network"):
        return _get_event_subgraph(db, project_id, chapter_id, book_id)

    # ----------------------------------------------------------------------
    # branch 7: story_entity —— 综合视图（人物/剧情线/事件/章节/世界观）
    # ----------------------------------------------------------------------
    # 仍然保留 SQL 路径以便开发环境（无 Neo4j）也能跑
    scoped_character_ids: set[int] | None = None
    if book_id is not None:
        scoped_character_ids = {
            char_id for (char_id,) in db.execute(
                select(Character.id).where(
                    Character.project_id == project_id,
                    Character.book_id == book_id,
                )
            ).all()
        }
        if not scoped_character_ids:
            return {"source": "sqlite-fallback", "nodes": [], "relationships": []}

    # === character ===
    rels_query = select(CharacterRelationship).where(CharacterRelationship.project_id == project_id)
    if book_id is not None:
        rels_query = rels_query.where(CharacterRelationship.book_id == book_id)
    if character_id is not None:
        rels_query = rels_query.where(
            or_(
                CharacterRelationship.source_character_id == character_id,
                CharacterRelationship.target_character_id == character_id,
            )
        )
    relationships = list(db.scalars(rels_query.order_by(CharacterRelationship.updated_at.desc())))
    char_ids = {r.source_character_id for r in relationships} | {r.target_character_id for r in relationships}
    if character_id is not None:
        char_ids.add(character_id)
    if scoped_character_ids is not None:
        char_ids = {cid for cid in char_ids if cid in scoped_character_ids}
    characters = list(db.scalars(select(Character).where(Character.id.in_(char_ids)))) if char_ids else []
    char_map = {c.id: c for c in characters}
    for c in characters:
        nodes.append({
            "id": f"character-{c.id}", "entity_id": c.id, "label": c.name, "type": "character",
            "meta": {"alias": c.alias, "role_type": c.role_type, "status": c.status},
        })
    for r in relationships:
        if r.source_character_id not in char_map or r.target_character_id not in char_map:
            continue
        edges.append({
            "id": f"rel-{r.id}",
            "source": f"character-{r.source_character_id}",
            "target": f"character-{r.target_character_id}",
            "type": r.relation_type,
            "meta": {"intensity": r.intensity, "status": r.status, "note": r.note},
        })

    # === plot_line (排除 story_arc) ===
    plot_query = select(PlotLine).where(
        PlotLine.project_id == project_id,
        or_(PlotLine.plot_type.is_(None), PlotLine.plot_type.in_(PLOT_REAL_PLOT_TYPES)),
    )
    if book_id is not None:
        plot_query = plot_query.where(PlotLine.book_id == book_id)
    plot_lines = list(db.scalars(plot_query))
    for p in plot_lines:
        nodes.append({
            "id": f"plot-{p.id}", "entity_id": p.id, "label": p.title, "type": "plot_line",
            "meta": {"plot_type": p.plot_type, "status": p.status, "priority": p.priority},
        })
        if p.chapter_id is not None:
            edges.append({
                "id": f"plot-chapter-{p.id}-{p.chapter_id}",
                "source": f"plot-{p.id}", "target": f"chapter-{p.chapter_id}",
                "type": "guides_chapter", "meta": {},
            })

    # === story_event + participation ===
    ev_query = select(StoryEvent).where(StoryEvent.project_id == project_id)
    if chapter_id is not None:
        ev_query = ev_query.where(StoryEvent.chapter_id == chapter_id)
    if book_id is not None:
        ev_query = ev_query.where(StoryEvent.book_id == book_id)
    story_events = list(db.scalars(ev_query))
    event_ids = {e.id for e in story_events}
    p_query = select(CharacterEventParticipation).where(
        CharacterEventParticipation.project_id == project_id,
    )
    if event_ids:
        p_query = p_query.where(CharacterEventParticipation.event_id.in_(event_ids))
    else:
        p_query = p_query.where(False)
    participations = list(db.scalars(p_query))
    for e in story_events:
        nodes.append({
            "id": f"event-{e.id}", "entity_id": e.id, "label": e.title, "type": "story_event",
            "meta": {"event_type": e.event_type, "status": e.status, "impact_level": e.impact_level},
        })
        if e.plot_line_id is not None:
            edges.append({
                "id": f"plot-event-{e.plot_line_id}-{e.id}",
                "source": f"plot-{e.plot_line_id}", "target": f"event-{e.id}",
                "type": "contains_event", "meta": {},
            })
        if e.chapter_id is not None:
            edges.append({
                "id": f"chapter-event-{e.chapter_id}-{e.id}",
                "source": f"chapter-{e.chapter_id}", "target": f"event-{e.id}",
                "type": "includes_event", "meta": {},
            })
    for p in participations:
        edges.append({
            "id": f"character-event-{p.character_id}-{p.event_id}-{p.role_type}",
            "source": f"character-{p.character_id}", "target": f"event-{p.event_id}",
            "type": p.role_type,
            "meta": {"impact_score": p.impact_score, "note": p.note},
        })

    # === chapter + chapter_plan + precedes / has_plan ===
    ch_query = select(Chapter).where(Chapter.project_id == project_id)
    if chapter_id is not None:
        ch_query = ch_query.where(Chapter.id == chapter_id)
    if book_id is not None:
        ch_query = ch_query.where(Chapter.book_id == book_id)
    chapters = list(db.scalars(ch_query.order_by(Chapter.chapter_no.is_(None).asc(), Chapter.chapter_no.asc())))
    for c in chapters:
        nodes.append({
            "id": f"chapter-{c.id}", "entity_id": c.id,
            "label": f"第{c.chapter_no}章 {c.title or ''}", "type": "chapter",
            "meta": {"status": c.status, "chapter_no": c.chapter_no},
        })
    for i, c in enumerate(chapters):
        if i + 1 < len(chapters):
            nxt = chapters[i + 1]
            edges.append({
                "id": f"chapter-precedes-{c.id}-{nxt.id}",
                "source": f"chapter-{c.id}", "target": f"chapter-{nxt.id}",
                "type": "precedes", "meta": {},
            })
    plan_query = select(ChapterPlan).where(ChapterPlan.project_id == project_id)
    if chapter_id is not None:
        plan_query = plan_query.where(ChapterPlan.chapter_id == chapter_id)
    if book_id is not None:
        scoped_chapter_ids = select(Chapter.id).where(
            Chapter.project_id == project_id, Chapter.book_id == book_id,
        )
        scoped_plot_ids = select(PlotLine.id).where(
            PlotLine.project_id == project_id, PlotLine.book_id == book_id,
        )
        plan_query = plan_query.where(
            or_(ChapterPlan.chapter_id.in_(scoped_chapter_ids), ChapterPlan.plot_line_id.in_(scoped_plot_ids)),
        )
    plans = list(db.scalars(plan_query))
    for pl in plans:
        nodes.append({
            "id": f"chapter-plan-{pl.id}", "entity_id": pl.id, "label": f"大纲: {pl.title or ''}",
            "type": "chapter_plan", "meta": {"status": pl.status, "selected_model": pl.selected_model},
        })
        if pl.chapter_id is not None:
            edges.append({
                "id": f"chapter-plan-link-{pl.chapter_id}-{pl.id}",
                "source": f"chapter-{pl.chapter_id}", "target": f"chapter-plan-{pl.id}",
                "type": "has_plan", "meta": {},
            })
        if pl.plot_line_id is not None:
            edges.append({
                "id": f"plot-plan-link-{pl.plot_line_id}-{pl.id}",
                "source": f"plot-{pl.plot_line_id}", "target": f"chapter-plan-{pl.id}",
                "type": "guides_plan", "meta": {},
            })

    # === worldbook (只读 category='worldbook' / NULL) ===
    wb_query = select(WorldbookEntry).where(
        WorldbookEntry.project_id == project_id,
        or_(
            WorldbookEntry.category.in_(WORLDBOOK_CATEGORIES),
            WorldbookEntry.category.is_(None),
        ),
    )
    if book_id is not None:
        wb_query = wb_query.where(WorldbookEntry.book_id == book_id)
    wb = list(db.scalars(wb_query.order_by(WorldbookEntry.updated_at.desc())))
    for entry in wb:
        nodes.append({
            "id": f"worldbook-{entry.id}", "entity_id": entry.id, "label": entry.title,
            "type": "worldbook_entry",
            "meta": {"category": entry.category, "source_type": entry.source_type, "source_ref": entry.source_ref},
        })

    return {"source": "sqlite-fallback", "nodes": nodes, "relationships": edges}


# ============================================================================
# Subgraph helpers — 每个 graph_type 一个独立函数，互不串台
# ============================================================================
def _get_story_arc_subgraph(db: Session, project_id: int, book_id: int | None) -> dict:
    """故事脉络子图：只读 StoryArc + StoryTheme + 涉及的 Chapter / Character。"""
    nodes: list[dict] = []
    edges: list[dict] = []

    arc_q = select(StoryArc).where(StoryArc.project_id == project_id)
    if book_id is not None:
        arc_q = arc_q.where(StoryArc.book_id == book_id)
    arcs = list(db.scalars(arc_q.order_by(StoryArc.priority.is_(None).asc(), StoryArc.priority.desc())))
    for a in arcs:
        nodes.append({
            "id": f"story-arc-{a.id}", "entity_id": a.id, "label": a.title, "type": "story_arc",
            "meta": {
                "arc_type": a.arc_type, "description": (a.description or "")[:200],
                "status": a.status, "priority": a.priority,
                "start_beat": (a.start_beat or "")[:120],
                "climax_beat": (a.climax_beat or "")[:120],
                "resolution_beat": (a.resolution_beat or "")[:120],
            },
        })

    theme_q = select(StoryTheme).where(StoryTheme.project_id == project_id)
    if book_id is not None:
        theme_q = theme_q.where(StoryTheme.book_id == book_id)
    themes = list(db.scalars(theme_q))
    for t in themes:
        nodes.append({
            "id": f"theme-{t.id}", "entity_id": t.id, "label": t.name, "type": "theme",
            "meta": {"description": (t.description or "")[:200], "represented_by": t.represented_by},
        })
    # arc-theme 关联：用 represented_by 反查（简化处理：theme.represented_by 包含 arc title 即可）
    for t in themes:
        represented = t.represented_by or "[]"
        for a in arcs:
            if a.title and a.title in represented:
                edges.append({
                    "id": f"arc-theme-{a.id}-{t.id}",
                    "source": f"story-arc-{a.id}", "target": f"theme-{t.id}",
                    "type": "embodies", "meta": {},
                })
                break
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}


def _get_character_subgraph(
    db: Session, project_id: int, character_id: int | None,
    book_id: int | None, chapter_id: int | None,
) -> dict:
    """人物关系子图：严格只显示 Character 节点 + RELATED_TO 边。"""
    nodes: list[dict] = []
    edges: list[dict] = []

    char_q = select(Character).where(Character.project_id == project_id)
    if book_id is not None:
        char_q = char_q.where(Character.book_id == book_id)
    if chapter_id is not None:
        char_q = char_q.where(Character.chapter_id == chapter_id)
    characters = list(db.scalars(char_q))
    char_ids = {c.id for c in characters}
    if character_id is not None:
        char_ids.add(character_id)

    rel_q = select(CharacterRelationship).where(CharacterRelationship.project_id == project_id)
    if book_id is not None:
        rel_q = rel_q.where(CharacterRelationship.book_id == book_id)
    if character_id is not None:
        rel_q = rel_q.where(or_(
            CharacterRelationship.source_character_id == character_id,
            CharacterRelationship.target_character_id == character_id,
        ))
    rels = list(db.scalars(rel_q))

    if character_id is not None:
        rel_char_ids = {r.source_character_id for r in rels} | {r.target_character_id for r in rels}
        char_ids |= rel_char_ids

    char_map = {c.id: c for c in characters}
    # 补全 char_map：关系里出现但 select 没拉出来的角色
    missing_ids = char_ids - set(char_map.keys())
    if missing_ids:
        for c in db.scalars(select(Character).where(Character.id.in_(missing_ids))):
            char_map[c.id] = c

    for cid, c in char_map.items():
        nodes.append({
            "id": f"character-{c.id}", "entity_id": c.id, "label": c.name, "type": "character",
            "meta": {"alias": c.alias, "role_type": c.role_type, "status": c.status},
        })
    for r in rels:
        if r.source_character_id not in char_map or r.target_character_id not in char_map:
            continue
        edges.append({
            "id": f"rel-{r.id}",
            "source": f"character-{r.source_character_id}",
            "target": f"character-{r.target_character_id}",
            "type": r.relation_type,
            "meta": {"intensity": r.intensity, "status": r.status, "note": r.note},
        })
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}


def _get_worldbook_subgraph(db: Session, project_id: int, book_id: int | None) -> dict:
    """世界观子图：只读 category='worldbook' 或 NULL 的 WorldbookEntry。"""
    nodes: list[dict] = []
    edges: list[dict] = []
    wb_q = select(WorldbookEntry).where(
        WorldbookEntry.project_id == project_id,
        or_(WorldbookEntry.category.in_(WORLDBOOK_CATEGORIES), WorldbookEntry.category.is_(None)),
    )
    if book_id is not None:
        wb_q = wb_q.where(WorldbookEntry.book_id == book_id)
    entries = list(db.scalars(wb_q.order_by(WorldbookEntry.updated_at.desc())))
    for e in entries:
        nodes.append({
            "id": f"worldbook-{e.id}", "entity_id": e.id, "label": e.title, "type": "worldbook_entry",
            "meta": {"category": e.category, "source_type": e.source_type, "source_ref": e.source_ref},
        })
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}


def _get_chapter_subgraph(
    db: Session, project_id: int, chapter_id: int | None, book_id: int | None,
) -> dict:
    """章节结构子图：Chapter + ChapterPlan + PRECEDES / HAS_PLAN 边。"""
    nodes: list[dict] = []
    edges: list[dict] = []

    ch_q = select(Chapter).where(Chapter.project_id == project_id)
    if chapter_id is not None:
        ch_q = ch_q.where(Chapter.id == chapter_id)
    if book_id is not None:
        ch_q = ch_q.where(Chapter.book_id == book_id)
    chapters = list(db.scalars(ch_q.order_by(Chapter.chapter_no.is_(None).asc(), Chapter.chapter_no.asc())))
    for c in chapters:
        nodes.append({
            "id": f"chapter-{c.id}", "entity_id": c.id,
            "label": f"第{c.chapter_no}章 {c.title or ''}", "type": "chapter",
            "meta": {"status": c.status, "chapter_no": c.chapter_no},
        })
    # 前后相继边
    for i, c in enumerate(chapters):
        if i + 1 < len(chapters):
            nxt = chapters[i + 1]
            edges.append({
                "id": f"chapter-precedes-{c.id}-{nxt.id}",
                "source": f"chapter-{c.id}", "target": f"chapter-{nxt.id}",
                "type": "precedes", "meta": {},
            })
    # 大纲节点
    pl_q = select(ChapterPlan).where(ChapterPlan.project_id == project_id)
    if chapter_id is not None:
        pl_q = pl_q.where(ChapterPlan.chapter_id == chapter_id)
    if book_id is not None:
        scoped_ch = select(Chapter.id).where(Chapter.project_id == project_id, Chapter.book_id == book_id)
        pl_q = pl_q.where(or_(ChapterPlan.chapter_id.in_(scoped_ch)))
    plans = list(db.scalars(pl_q))
    for p in plans:
        nodes.append({
            "id": f"chapter-plan-{p.id}", "entity_id": p.id,
            "label": f"大纲: {p.title or ''}", "type": "chapter_plan",
            "meta": {"status": p.status, "selected_model": p.selected_model},
        })
        if p.chapter_id is not None:
            edges.append({
                "id": f"chapter-plan-link-{p.chapter_id}-{p.id}",
                "source": f"chapter-{p.chapter_id}", "target": f"chapter-plan-{p.id}",
                "type": "has_plan", "meta": {},
            })
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}


def _get_plot_subgraph(
    db: Session, project_id: int, chapter_id: int | None, book_id: int | None,
) -> dict:
    """情节脉络子图：只读 plot_line (排除 story_arc) + GUIDES_CHAPTER 边。"""
    nodes: list[dict] = []
    edges: list[dict] = []
    pl_q = select(PlotLine).where(
        PlotLine.project_id == project_id,
        or_(PlotLine.plot_type.is_(None), PlotLine.plot_type.in_(PLOT_REAL_PLOT_TYPES)),
    )
    if book_id is not None:
        pl_q = pl_q.where(PlotLine.book_id == book_id)
    if chapter_id is not None:
        pl_q = pl_q.where(PlotLine.chapter_id == chapter_id)
    plots = list(db.scalars(pl_q.order_by(PlotLine.priority.is_(None).asc(), PlotLine.priority.desc())))
    for p in plots:
        nodes.append({
            "id": f"plot-{p.id}", "entity_id": p.id, "label": p.title, "type": "plot_line",
            "meta": {"plot_type": p.plot_type, "status": p.status, "priority": p.priority},
        })
        if p.chapter_id is not None:
            edges.append({
                "id": f"plot-chapter-{p.id}-{p.chapter_id}",
                "source": f"plot-{p.id}", "target": f"chapter-{p.chapter_id}",
                "type": "guides_chapter", "meta": {},
            })
    # 同一章下的 plot_line 之间建立 intersects_with 边
    chapter_to_plots: dict[int, list[int]] = {}
    for p in plots:
        if p.chapter_id is not None:
            chapter_to_plots.setdefault(p.chapter_id, []).append(p.id)
    seen: set[tuple[int, int]] = set()
    for ch_id, pids in chapter_to_plots.items():
        if len(pids) < 2:
            continue
        for i in range(len(pids)):
            for j in range(i + 1, len(pids)):
                a, b = sorted([pids[i], pids[j]])
                key = (a, b)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({
                    "id": f"plot-intersects-{a}-{b}",
                    "source": f"plot-{a}", "target": f"plot-{b}",
                    "type": "intersects_with", "meta": {"via": "shared_chapter", "chapter_id": ch_id},
                })
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}


def _get_event_subgraph(
    db: Session, project_id: int, chapter_id: int | None, book_id: int | None,
) -> dict:
    """事件网络子图：StoryEvent + Character-PARTICIPATES_IN + StoryEvent-INCLUDES_CHAPTER。"""
    nodes: list[dict] = []
    edges: list[dict] = []
    ev_q = select(StoryEvent).where(StoryEvent.project_id == project_id)
    if chapter_id is not None:
        ev_q = ev_q.where(StoryEvent.chapter_id == chapter_id)
    if book_id is not None:
        ev_q = ev_q.where(StoryEvent.book_id == book_id)
    events = list(db.scalars(ev_q))
    event_ids = {e.id for e in events}
    for e in events:
        nodes.append({
            "id": f"event-{e.id}", "entity_id": e.id, "label": e.title, "type": "story_event",
            "meta": {"event_type": e.event_type, "status": e.status, "impact_level": e.impact_level},
        })
        if e.chapter_id is not None:
            edges.append({
                "id": f"event-includes-chapter-{e.id}-{e.chapter_id}",
                "source": f"event-{e.id}", "target": f"chapter-{e.chapter_id}",
                "type": "in_chapter", "meta": {},
            })
    p_q = select(CharacterEventParticipation).where(
        CharacterEventParticipation.project_id == project_id,
        CharacterEventParticipation.event_id.in_(event_ids) if event_ids else False,
    )
    participations = list(db.scalars(p_q))
    for p in participations:
        edges.append({
            "id": f"character-event-{p.character_id}-{p.event_id}-{p.role_type}",
            "source": f"character-{p.character_id}", "target": f"event-{p.event_id}",
            "type": p.role_type,
            "meta": {"impact_score": p.impact_score, "note": p.note},
        })
    return {"source": "sql-authoritative", "nodes": nodes, "relationships": edges}
