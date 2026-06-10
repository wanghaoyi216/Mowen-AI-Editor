from pathlib import Path
import sys

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.base import SessionLocal, create_db_and_tables
from app.models.character import Character
from app.models.plot_line import PlotLine
from app.models.project import NovelProject
from app.models.story_event import StoryEvent
from app.schemas.character_event import CharacterEventParticipationCreate
from app.services.character_event_service import create_event_participation
from app.services.react_executor_service import execute_minimal_react_task


def main() -> None:
    create_db_and_tables()
    db = SessionLocal()
    try:
        project = db.scalar(select(NovelProject).where(NovelProject.name == "Demo Novel Project"))
        if project is None:
            print("Demo project not found. Run scripts/seed_demo.py first.")
            return

        plot_line = db.scalar(select(PlotLine).where(PlotLine.project_id == project.id).where(PlotLine.title == "审判裂缝主线"))
        if plot_line is None:
            plot_line = PlotLine(
                project_id=project.id,
                title="审判裂缝主线",
                plot_type="main",
                summary="围绕审判体系内部裂缝逐步揭露的主线。",
                goal="揭露制度内部第二股势力。",
                conflict="秩序维持者和真相追查者发生冲突。",
                stakes="主角一旦失败将失去全部线索。",
                status="planned",
                priority=10,
            )
            db.add(plot_line)
            db.commit()
            db.refresh(plot_line)

        event = db.scalar(select(StoryEvent).where(StoryEvent.project_id == project.id).where(StoryEvent.title == "雨夜审讯"))
        if event is None:
            event = StoryEvent(
                project_id=project.id,
                plot_line_id=plot_line.id,
                title="雨夜审讯",
                event_type="interrogation",
                summary="主角通过一次危险审讯，首次确认审判署存在隐秘势力。",
                trigger_condition="嫌疑人愿意交换情报",
                expected_outcome="主角获得半真半假的核心线索",
                impact_level=5,
                status="planned",
            )
            db.add(event)
            db.commit()
            db.refresh(event)

        characters = {
            character.name: character
            for character in db.scalars(select(Character).where(Character.project_id == project.id))
        }
        participation_specs = [
            ("林雾", "witness", 0.9, "作为观察者和套话者参与事件。"),
            ("顾沉", "controller", 0.8, "掌控审讯节奏并隐藏部分真相。"),
        ]
        for character_name, role_type, impact_score, note in participation_specs:
            character = characters.get(character_name)
            if character is None:
                continue
            create_event_participation(
                db,
                project.id,
                CharacterEventParticipationCreate(
                    character_id=character.id,
                    event_id=event.id,
                    role_type=role_type,
                    impact_score=impact_score,
                    note=note,
                ),
            )

        result = execute_minimal_react_task(
            db,
            project_id=project.id,
            title="设计雨夜审讯章节任务流",
            module_type="chapter_writing",
            objective="为“雨夜审讯”事件生成一个最小 ReAct 章节执行链。",
            plot_line_id=plot_line.id,
        )
        print(f"Seeded event participation and ReAct task: task_id={result['task'].id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
