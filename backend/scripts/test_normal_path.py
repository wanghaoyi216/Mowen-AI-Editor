"""正常路径：Tavily 真实可用下应该走 Tavily。"""
import os
import sys
import json

sys.path.insert(0, "/app")

# 不覆盖环境变量，让 .env 的真实 key 生效
from app.db.base import SessionLocal
from app.models.project import NovelProject
from app.services.trend_service import execute_trend_exploration
from app.models.trend_exploration import TrendExploration

db = SessionLocal()
try:
    project = db.query(NovelProject).first()
    project_id = project.id
    print(f"使用 project_id={project_id}")

    db.query(TrendExploration).filter(TrendExploration.project_id == project_id).delete()
    db.commit()

    print("\n===== 正常路径：Tavily 真实 key =====")
    trend = execute_trend_exploration(
        db,
        project_id=project_id,
        title="正常路径验证",
        query_text="修仙 小说 趋势",
        max_results=5,
    )
    raw = json.loads(trend.raw_findings)
    print(f"source       = {raw.get('source')}")
    print(f"fallback_chain= {raw.get('fallback_chain')}")
    print(f"topics 数    = {len(raw.get('sources', []))}")
    for i, s in enumerate(raw.get('sources', [])[:2]):
        print(f"  [{i}] {s.get('title', '?')[:80]}")

    if raw.get("source") == "tavily":
        print("\n✅ 正常路径：Tavily 优先拿到结果")
    else:
        print(f"\n⚠️ 实际走了 {raw.get('source')}")
finally:
    db.close()
