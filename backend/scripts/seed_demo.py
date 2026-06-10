from pathlib import Path
import sys

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.base import SessionLocal, create_db_and_tables
from app.models.character import Character
from app.models.character_relationship import CharacterRelationship
from app.models.project import NovelProject
from app.schemas.graph import CharacterRelationshipCreate
from app.services.graph_service import create_character_relationship, sync_character_to_neo4j


def main() -> None:
    create_db_and_tables()
    db = SessionLocal()
    try:
        project = db.scalar(select(NovelProject).where(NovelProject.name == "Demo Novel Project"))
        if project is None:
            project = NovelProject(
                name="Demo Novel Project",
                genre="悬疑奇幻",
                theme="禁术审判与秩序裂缝",
                target_audience="网文读者",
                writing_style="紧张、克制、悬疑推进",
                tone="暗色、克制、压迫感",
                summary="用于演示角色关系图谱和章节工作流的样例项目。",
                world_setting="蒸汽都市与审判体系并存的近代奇幻世界。",
            )
            db.add(project)
            db.commit()
            db.refresh(project)

        characters_by_name = {
            character.name: character
            for character in db.scalars(select(Character).where(Character.project_id == project.id))
        }
        seed_characters = [
            {"name": "林雾", "role_type": "protagonist", "identity": "档案记录员", "status": "active"},
            {"name": "顾沉", "role_type": "executor", "identity": "审判署执行官", "status": "active"},
            {"name": "闻柯", "role_type": "informant", "identity": "地下情报商", "status": "active"},
        ]

        for payload in seed_characters:
            if payload["name"] in characters_by_name:
                continue
            character = Character(project_id=project.id, **payload)
            db.add(character)
            db.commit()
            db.refresh(character)
            sync_character_to_neo4j(character)
            characters_by_name[character.name] = character

        existing_pairs = {
            (item.source_character_id, item.target_character_id, item.relation_type)
            for item in db.scalars(select(CharacterRelationship).where(CharacterRelationship.project_id == project.id))
        }

        relationship_specs = [
            ("林雾", "顾沉", "猜疑", 0.8, "互相试探，但必须合作。"),
            ("顾沉", "林雾", "保护", 0.6, "出于职责之外的隐性保护。"),
            ("林雾", "闻柯", "交易", 0.9, "通过秘密档案换取情报。"),
        ]
        for source_name, target_name, relation_type, intensity, note in relationship_specs:
            source = characters_by_name[source_name]
            target = characters_by_name[target_name]
            if (source.id, target.id, relation_type) in existing_pairs:
                continue
            create_character_relationship(
                db,
                project.id,
                CharacterRelationshipCreate(
                    source_character_id=source.id,
                    target_character_id=target.id,
                    relation_type=relation_type,
                    intensity=intensity,
                    note=note,
                ),
            )
            existing_pairs.add((source.id, target.id, relation_type))

        print(f"Seeded demo project: {project.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
