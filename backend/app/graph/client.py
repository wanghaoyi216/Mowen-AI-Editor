from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from app.core.config import settings


class Neo4jClient:
    def __init__(self, uri: str, database: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    def is_available(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def upsert_character(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_character_tx, payload)

    def upsert_relationship(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_relationship_tx, payload)

    def upsert_plot_line(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_plot_line_tx, payload)

    def upsert_chapter(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_chapter_tx, payload)

    def upsert_story_event(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_story_event_tx, payload)

    def upsert_chapter_plan(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_chapter_plan_tx, payload)

    def upsert_character_event_participation(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_character_event_participation_tx, payload)

    def upsert_worldbook_entry(self, payload: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_worldbook_entry_tx, payload)

    def upsert_story_arc(self, payload: dict) -> None:
        """同步 StoryArc 节点到 Neo4j。"""
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_story_arc_tx, payload)

    def upsert_story_theme(self, payload: dict) -> None:
        """同步 StoryTheme 节点到 Neo4j。"""
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._upsert_story_theme_tx, payload)

    def get_character_graph(
        self,
        project_id: int,
        character_id: int | None = None,
    ) -> dict:
        with self._driver.session(database=self._database) as session:
            return session.execute_read(self._get_character_graph_tx, project_id, character_id)

    def get_mixed_graph(
        self,
        project_id: int,
        character_id: int | None = None,
        chapter_id: int | None = None,
        graph_type: str = "story_entity",
    ) -> dict:
        with self._driver.session(database=self._database) as session:
            return session.execute_read(
                self._get_mixed_graph_tx,
                project_id,
                character_id,
                chapter_id,
                graph_type,
            )

    def get_story_arc_graph(
        self,
        project_id: int,
    ) -> dict:
        with self._driver.session(database=self._database) as session:
            return session.execute_read(self._get_story_arc_graph_tx, project_id)

    def close(self) -> None:
        self._driver.close()

    @staticmethod
    def _upsert_character_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (c:Character {project_id: $project_id, character_id: $character_id})
            SET c.book_id = $book_id,
                c.name = $name,
                c.alias = $alias,
                c.role_type = $role_type,
                c.status = $status
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_relationship_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (source:Character {project_id: $project_id, character_id: $source_character_id})
            ON CREATE SET source.name = $source_name, source.book_id = $book_id
            MERGE (target:Character {project_id: $project_id, character_id: $target_character_id})
            ON CREATE SET target.name = $target_name, target.book_id = $book_id
            MERGE (source)-[r:RELATED_TO {
                project_id: $project_id,
                source_character_id: $source_character_id,
                target_character_id: $target_character_id,
                relation_type: $relation_type
            }]->(target)
            SET r.book_id = $book_id,
                r.intensity = $intensity,
                r.status = $status,
                r.note = $note
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_plot_line_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (p:PlotLine {project_id: $project_id, plot_line_id: $plot_line_id})
            SET p.book_id = $book_id,
                p.chapter_id = $chapter_id,
                p.title = $title,
                p.plot_type = $plot_type,
                p.status = $status,
                p.priority = $priority
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_chapter_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (c:Chapter {project_id: $project_id, chapter_id: $chapter_id})
            SET c.book_id = $book_id,
                c.title = $title,
                c.chapter_no = $chapter_no,
                c.status = $status
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_story_event_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (e:StoryEvent {project_id: $project_id, event_id: $event_id})
            SET e.book_id = $book_id,
                e.title = $title,
                e.event_type = $event_type,
                e.status = $status,
                e.impact_level = $impact_level
            WITH e
            OPTIONAL MATCH (p:PlotLine {project_id: $project_id, plot_line_id: $plot_line_id})
            FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
                MERGE (p)-[:CONTAINS_EVENT {project_id: $project_id}]->(e)
            )
            WITH e
            OPTIONAL MATCH (c:Chapter {project_id: $project_id, chapter_id: $chapter_id})
            FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:INCLUDES_EVENT {project_id: $project_id}]->(e)
            )
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_chapter_plan_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (cp:ChapterPlan {project_id: $project_id, chapter_plan_id: $chapter_plan_id})
            SET cp.book_id = $book_id,
                cp.title = $title,
                cp.status = $status,
                cp.selected_model = $selected_model
            WITH cp
            OPTIONAL MATCH (c:Chapter {project_id: $project_id, chapter_id: $chapter_id})
            FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:HAS_PLAN {project_id: $project_id}]->(cp)
            )
            WITH cp
            OPTIONAL MATCH (p:PlotLine {project_id: $project_id, plot_line_id: $plot_line_id})
            FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
                MERGE (p)-[:GUIDES_PLAN {project_id: $project_id}]->(cp)
            )
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_character_event_participation_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MATCH (c:Character {project_id: $project_id, character_id: $character_id})
            MATCH (e:StoryEvent {project_id: $project_id, event_id: $event_id})
            MERGE (c)-[r:PARTICIPATES_IN {
                project_id: $project_id,
                character_id: $character_id,
                event_id: $event_id,
                role_type: $role_type
            }]->(e)
            SET r.book_id = $book_id,
                r.impact_score = $impact_score,
                r.note = $note
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_worldbook_entry_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (w:WorldbookEntry {project_id: $project_id, worldbook_entry_id: $worldbook_entry_id})
            SET w.book_id = $book_id,
                w.title = $title,
                w.category = $category,
                w.content = $content,
                w.source_type = $source_type,
                w.source_ref = $source_ref
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_story_arc_tx(tx, payload: dict) -> None:
        """StoryArc 节点。带 has_character / has_event 边的批量同步逻辑由调用方
        负责（sync_story_arc_to_neo4j 会在 upsert_story_arc 之后再单建关系）。"""
        tx.run(
            """
            MERGE (a:StoryArc {project_id: $project_id, story_arc_id: $story_arc_id})
            SET a.book_id = $book_id,
                a.title = $title,
                a.arc_type = $arc_type,
                a.description = $description,
                a.start_beat = $start_beat,
                a.climax_beat = $climax_beat,
                a.resolution_beat = $resolution_beat,
                a.status = $status,
                a.priority = $priority
            """,
            **payload,
        ).consume()

    @staticmethod
    def _upsert_story_theme_tx(tx, payload: dict) -> None:
        tx.run(
            """
            MERGE (t:StoryTheme {project_id: $project_id, story_theme_id: $story_theme_id})
            SET t.book_id = $book_id,
                t.name = $name,
                t.description = $description,
                t.represented_by = $represented_by,
                t.arc_connection = $arc_connection
            """,
            **payload,
        ).consume()

    @staticmethod
    def _get_character_graph_tx(tx, project_id: int, character_id: int | None) -> dict:
        records = tx.run(
            """
            MATCH (source:Character {project_id: $project_id})-[r:RELATED_TO {project_id: $project_id}]->(target:Character {project_id: $project_id})
            WHERE $character_id IS NULL
               OR source.character_id = $character_id
               OR target.character_id = $character_id
            RETURN source, r, target
            ORDER BY source.name, target.name
            """,
            project_id=project_id,
            character_id=character_id,
        )

        nodes_by_key: dict[str, dict] = {}
        relationships: list[dict] = []
        for record in records:
            source = record["source"]
            target = record["target"]
            relationship = record["r"]
            source_key = f"character-{source['character_id']}"
            target_key = f"character-{target['character_id']}"
            nodes_by_key[source_key] = {
                "id": source_key,
                "entity_id": source["character_id"],
                "label": source.get("name", ""),
                "type": "character",
                "meta": {
                    "alias": source.get("alias"),
                    "role_type": source.get("role_type"),
                    "status": source.get("status"),
                },
            }
            nodes_by_key[target_key] = {
                "id": target_key,
                "entity_id": target["character_id"],
                "label": target.get("name", ""),
                "type": "character",
                "meta": {
                    "alias": target.get("alias"),
                    "role_type": target.get("role_type"),
                    "status": target.get("status"),
                },
            }
            relationships.append(
                {
                    "id": f"rel-{relationship['source_character_id']}-{relationship['target_character_id']}-{relationship['relation_type']}",
                    "source": source_key,
                    "target": target_key,
                    "type": relationship["relation_type"],
                    "meta": {
                        "intensity": relationship.get("intensity"),
                        "status": relationship.get("status"),
                        "note": relationship.get("note"),
                    },
                }
            )

        return {"nodes": list(nodes_by_key.values()), "relationships": relationships}

    @staticmethod
    def _get_mixed_graph_tx(
        tx,
        project_id: int,
        character_id: int | None,
        chapter_id: int | None,
        graph_type: str,
    ) -> dict:
        """按 graph_type 返回对应子图。
        严格的节点/边白名单 —— 早期版本会把 'story_arc' 误带 'Character'，
        把 'plot' 误带 'plot_type="story_arc"' 的 PlotLine，把 'worldbook'
        误带 'category="story_event"|"theme"' 的条目。本次按 graph_type 严格分流：
            story_entity       -> Character + PlotLine + StoryEvent + Chapter + ChapterPlan + WorldbookEntry
            character          -> Character + RELATED_TO
            plot / plot_line   -> PlotLine(plot_type in (plot_line, subplot, chapter_scene))
                                 + PlotLine->Chapter (GUIDES_CHAPTER) 边
            event / event_network -> StoryEvent + Character-PARTICIPATES_IN 边
            chapter / chapter_structure -> Chapter + ChapterPlan + HAS_PLAN/PRECEDES 边
            worldbook / worldview -> WorldbookEntry (category='worldbook') 内部
            story_arc / arc    -> StoryArc + StoryTheme + (可选) Character 边
        """
        records = tx.run(
            """
            MATCH (n {project_id: $project_id})
            WHERE
                ($graph_type = 'story_entity'
                    AND any(label IN labels(n) WHERE label IN [
                        'Character', 'PlotLine', 'StoryEvent',
                        'Chapter', 'ChapterPlan', 'WorldbookEntry'
                    ]))
                OR ($graph_type = 'character'
                    AND 'Character' IN labels(n))
                OR ($graph_type IN ('plot', 'plot_line')
                    AND 'PlotLine' IN labels(n)
                    AND (n.plot_type IS NULL OR n.plot_type IN ('plot_line', 'subplot', 'chapter_scene', 'main_plot')))
                OR ($graph_type IN ('event', 'event_network')
                    AND 'StoryEvent' IN labels(n))
                OR ($graph_type IN ('chapter', 'chapter_structure', 'chapter_plan')
                    AND any(label IN labels(n) WHERE label IN ['Chapter', 'ChapterPlan']))
                OR ($graph_type IN ('worldbook', 'worldview')
                    AND 'WorldbookEntry' IN labels(n)
                    AND (n.category = 'worldbook' OR n.category IS NULL))
                OR ($graph_type IN ('story_arc', 'arc')
                    AND any(label IN labels(n) WHERE label IN ['StoryArc', 'StoryTheme']))
            OPTIONAL MATCH (n)-[r]->(m {project_id: $project_id})
            WHERE
                ($graph_type = 'story_entity'
                    AND any(label IN labels(m) WHERE label IN [
                        'Character', 'PlotLine', 'StoryEvent',
                        'Chapter', 'ChapterPlan', 'WorldbookEntry'
                    ]))
                OR ($graph_type = 'character'
                    AND 'Character' IN labels(m))
                OR ($graph_type IN ('plot', 'plot_line')
                    AND 'PlotLine' IN labels(m)
                    AND (m.plot_type IS NULL OR m.plot_type IN ('plot_line', 'subplot', 'chapter_scene', 'main_plot'))
                    AND any(label IN labels(n) WHERE label IN ['PlotLine', 'Chapter', 'Character']))
                OR ($graph_type IN ('event', 'event_network')
                    AND (any(label IN labels(m) WHERE label IN ['StoryEvent', 'Character', 'Chapter'])))
                OR ($graph_type IN ('chapter', 'chapter_structure', 'chapter_plan')
                    AND any(label IN labels(m) WHERE label IN ['Chapter', 'ChapterPlan']))
                OR ($graph_type IN ('worldbook', 'worldview')
                    AND 'WorldbookEntry' IN labels(m)
                    AND (m.category = 'worldbook' OR m.category IS NULL))
                OR ($graph_type IN ('story_arc', 'arc')
                    AND any(label IN labels(m) WHERE label IN ['StoryArc', 'StoryTheme', 'Chapter', 'Character']))
            WITH n, r, m
            WHERE
                ($character_id IS NULL
                    OR ('Character' IN labels(n) AND n.character_id = $character_id)
                    OR ('Character' IN labels(m) AND m.character_id = $character_id))
                AND ($chapter_id IS NULL
                    OR ('Chapter' IN labels(n) AND n.chapter_id = $chapter_id)
                    OR ('Chapter' IN labels(m) AND m.chapter_id = $chapter_id))
            RETURN n, r, m
            """,
            project_id=project_id,
            character_id=character_id,
            chapter_id=chapter_id,
            graph_type=graph_type,
        )

        nodes_by_key: dict[str, dict] = {}
        relationships: list[dict] = []

        def to_node(node) -> dict | None:
            if node is None:
                return None
            labels = set(node.labels)
            if "Character" in labels:
                return {
                    "id": f"character-{node['character_id']}",
                    "entity_id": node["character_id"],
                    "label": node.get("name", ""),
                    "type": "character",
                    "meta": {
                        "alias": node.get("alias"),
                        "role_type": node.get("role_type"),
                        "status": node.get("status"),
                    },
                }
            if "PlotLine" in labels:
                return {
                    "id": f"plot-{node['plot_line_id']}",
                    "entity_id": node["plot_line_id"],
                    "label": node.get("title", ""),
                    "type": "plot_line",
                    "meta": {
                        "plot_type": node.get("plot_type"),
                        "status": node.get("status"),
                        "priority": node.get("priority"),
                    },
                }
            if "StoryEvent" in labels:
                return {
                    "id": f"event-{node['event_id']}",
                    "entity_id": node["event_id"],
                    "label": node.get("title", ""),
                    "type": "story_event",
                    "meta": {
                        "event_type": node.get("event_type"),
                        "status": node.get("status"),
                        "impact_level": node.get("impact_level"),
                    },
                }
            if "Chapter" in labels:
                return {
                    "id": f"chapter-{node['chapter_id']}",
                    "entity_id": node["chapter_id"],
                    "label": f"第{node.get('chapter_no', '')}章 {node.get('title', '')}",
                    "type": "chapter",
                    "meta": {
                        "chapter_no": node.get("chapter_no"),
                        "status": node.get("status"),
                    },
                }
            if "ChapterPlan" in labels:
                return {
                    "id": f"chapter-plan-{node['chapter_plan_id']}",
                    "entity_id": node["chapter_plan_id"],
                    "label": f"大纲: {node.get('title', '')}",
                    "type": "chapter_plan",
                    "meta": {
                        "status": node.get("status"),
                        "selected_model": node.get("selected_model"),
                    },
                }
            if "WorldbookEntry" in labels:
                return {
                    "id": f"worldbook-{node['worldbook_entry_id']}",
                    "entity_id": node["worldbook_entry_id"],
                    "label": node.get("title", ""),
                    "type": "worldbook_entry",
                    "meta": {
                        "category": node.get("category"),
                        "source_type": node.get("source_type"),
                        "source_ref": node.get("source_ref"),
                    },
                }
            if "StoryArc" in labels:
                return {
                    "id": f"story-arc-{node['story_arc_id']}",
                    "entity_id": node["story_arc_id"],
                    "label": node.get("title", ""),
                    "type": "story_arc",
                    "meta": {
                        "arc_type": node.get("arc_type"),
                        "description": (node.get("description") or "")[:200],
                        "status": node.get("status"),
                        "priority": node.get("priority"),
                    },
                }
            if "StoryTheme" in labels:
                return {
                    "id": f"theme-{node['story_theme_id']}",
                    "entity_id": node["story_theme_id"],
                    "label": node.get("name", ""),
                    "type": "theme",
                    "meta": {
                        "description": (node.get("description") or "")[:200],
                        "represented_by": node.get("represented_by"),
                    },
                }
            return None

        def relationship_id(rel, source_id: str, target_id: str) -> str:
            if rel.type == "RELATED_TO":
                return f"rel-{rel.get('source_character_id')}-{rel.get('target_character_id')}-{rel.get('relation_type')}"
            if rel.type == "PARTICIPATES_IN":
                return f"character-event-{rel.get('character_id')}-{rel.get('event_id')}-{rel.get('role_type')}"
            return f"{rel.type.lower()}-{source_id}-{target_id}"

        def relationship_type(rel) -> str:
            if rel.type == "RELATED_TO":
                return rel.get("relation_type", "related_to")
            if rel.type == "PARTICIPATES_IN":
                return rel.get("role_type", "participates_in")
            return rel.type.lower()

        def relationship_meta(rel) -> dict:
            if rel.type == "RELATED_TO":
                return {
                    "intensity": rel.get("intensity"),
                    "status": rel.get("status"),
                    "note": rel.get("note"),
                }
            if rel.type == "PARTICIPATES_IN":
                return {
                    "impact_score": rel.get("impact_score"),
                    "note": rel.get("note"),
                }
            return {}

        for record in records:
            source_node = to_node(record["n"])
            target_node = to_node(record["m"])
            if source_node is not None:
                nodes_by_key[source_node["id"]] = source_node
            if target_node is not None:
                nodes_by_key[target_node["id"]] = target_node

            rel = record["r"]
            if rel is not None and source_node is not None and target_node is not None:
                relationships.append(
                    {
                        "id": relationship_id(rel, source_node["id"], target_node["id"]),
                        "source": source_node["id"],
                        "target": target_node["id"],
                        "type": relationship_type(rel),
                        "meta": relationship_meta(rel),
                    }
                )

        return {"nodes": list(nodes_by_key.values()), "relationships": relationships}

    @staticmethod
    def _get_story_arc_graph_tx(tx, project_id: int) -> dict:
        """获取"故事脉络"子图：只返回 StoryArc + StoryTheme + 涉及的 Chapter / Character。
        旧版本会把 ``PlotLine(plot_type='story_arc')`` 与 ``WorldbookEntry(category='theme')`` 也混进
        来。本次按新表读，已经没有旧数据干扰。
        """
        records = tx.run(
            """
            MATCH (n {project_id: $project_id})
            WHERE any(label IN labels(n) WHERE label IN ['StoryArc', 'StoryTheme'])
            OPTIONAL MATCH (n)-[r]->(m {project_id: $project_id})
            WHERE any(label IN labels(m) WHERE label IN ['StoryArc', 'StoryTheme', 'Chapter', 'Character'])
            RETURN n, r, m
            """,
            project_id=project_id,
        )

        nodes_by_key: dict[str, dict] = {}
        relationships: list[dict] = []

        def to_arc_node(node) -> dict | None:
            if node is None:
                return None
            labels = set(node.labels)
            if "StoryArc" in labels:
                return {
                    "id": f"story-arc-{node['story_arc_id']}",
                    "entity_id": node["story_arc_id"],
                    "label": node.get("title", ""),
                    "type": "story_arc",
                    "meta": {
                        "arc_type": node.get("arc_type"),
                        "description": (node.get("description") or "")[:200],
                        "status": node.get("status"),
                        "priority": node.get("priority"),
                        "start_beat": (node.get("start_beat") or "")[:120],
                        "climax_beat": (node.get("climax_beat") or "")[:120],
                        "resolution_beat": (node.get("resolution_beat") or "")[:120],
                    },
                }
            if "StoryTheme" in labels:
                return {
                    "id": f"theme-{node['story_theme_id']}",
                    "entity_id": node["story_theme_id"],
                    "label": node.get("name", ""),
                    "type": "theme",
                    "meta": {
                        "description": (node.get("description") or "")[:200],
                        "represented_by": node.get("represented_by"),
                    },
                }
            if "Chapter" in labels:
                return {
                    "id": f"chapter-{node['chapter_id']}",
                    "entity_id": node["chapter_id"],
                    "label": f"第{node.get('chapter_no', '')}章 {node.get('title', '')}",
                    "type": "chapter",
                    "meta": {
                        "chapter_no": node.get("chapter_no"),
                        "status": node.get("status"),
                    },
                }
            if "Character" in labels:
                return {
                    "id": f"character-{node['character_id']}",
                    "entity_id": node["character_id"],
                    "label": node.get("name", ""),
                    "type": "character",
                    "meta": {
                        "role_type": node.get("role_type"),
                        "status": node.get("status"),
                    },
                }
            return None

        for record in records:
            source_node = to_arc_node(record["n"])
            target_node = to_arc_node(record["m"])
            if source_node is not None:
                nodes_by_key[source_node["id"]] = source_node
            if target_node is not None:
                nodes_by_key[target_node["id"]] = target_node

            rel = record["r"]
            if rel is not None and source_node is not None and target_node is not None:
                relationships.append(
                    {
                        "id": f"arc-rel-{source_node['id']}-{target_node['id']}-{rel.type}",
                        "source": source_node["id"],
                        "target": target_node["id"],
                        "type": rel.type.lower(),
                        "meta": {},
                    }
                )

        return {"nodes": list(nodes_by_key.values()), "relationships": relationships}


def swallow_neo4j_error(error: Exception) -> bool:
    return isinstance(error, Neo4jError)


def build_neo4j_client() -> Neo4jClient:
    return Neo4jClient(settings.neo4j_uri, settings.neo4j_database, settings.neo4j_user, settings.neo4j_password)
