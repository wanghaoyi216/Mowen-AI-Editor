"""验证修复 1：delete_task 是否级联清空 TrendExploration。"""
import sys
sys.path.insert(0, "/app")

from app.db.base import SessionLocal
from app.models.ai_task import AITask, TaskLog, TaskStep
from app.models.trend_exploration import TrendExploration
from app.models.project import NovelProject
from app.services.task_service import create_task, delete_task
from app.schemas.ai_task import AITaskCreate
from app.schemas.trend_exploration import TrendExplorationCreate
from app.services.trend_service import create_trend

db = SessionLocal()
try:
    # 1. 找一个现有项目
    project = db.query(NovelProject).first()
    if project is None:
        print("没有可用项目，先建一个")
        sys.exit(0)
    project_id = project.id
    print(f"使用 project_id={project_id}")

    # 2. 现状
    trends_before = db.query(TrendExploration).filter(TrendExploration.project_id == project_id).count()
    tasks_before = db.query(AITask).filter(AITask.project_id == project_id).count()
    print(f"操作前: trends={trends_before}, tasks={tasks_before}")

    # 3. 创建一个 trend（模拟热点探索产生的记录）
    trend = create_trend(db, project_id, TrendExplorationCreate(
        title="测试趋势",
        query_text="测试查询",
        source_scope="web",
    ))
    print(f"  + 创建 trend id={trend.id}")

    # 4. 创建一个 task
    task = create_task(db, project_id, AITaskCreate(
        title="测试任务",
        task_type="trend_exploration",
        module_type="trend_exploration",
        status="completed",
    ))
    print(f"  + 创建 task id={task.id}")

    trends_mid = db.query(TrendExploration).filter(TrendExploration.project_id == project_id).count()
    tasks_mid = db.query(AITask).filter(AITask.project_id == project_id).count()
    print(f"创建后: trends={trends_mid}, tasks={tasks_mid}")

    # 5. 删除 task（关键：trend_exploration 应该也被清空）
    ok = delete_task(db, project_id, task.id)
    print(f"  - delete_task 返回: {ok}")

    trends_after = db.query(TrendExploration).filter(TrendExploration.project_id == project_id).count()
    tasks_after = db.query(AITask).filter(AITask.project_id == project_id).count()
    print(f"删除 task 后: trends={trends_after}, tasks={tasks_after}")

    if trends_after == 0 and tasks_after == tasks_before:
        print("✅ 验证通过：删除 task 时 trend_exploration 也被级联清空")
    else:
        print("❌ 验证失败：")
        if trends_after != 0:
            print(f"   trend_exploration 期望=0 实际={trends_after}")
        if tasks_after != tasks_before:
            print(f"   tasks 期望={tasks_before} 实际={tasks_after}")
finally:
    db.close()
