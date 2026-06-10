"""端到端验证：执行热点探索，强制让 Tavily 失败，看是否降级到 DuckDuckGo/离线兜底。

策略：把 TAVILY_KEY 设成假 key 让 Tavily 401 报错（不修改 .env，临时覆盖环境变量）。
"""
import os
import sys
import json

sys.path.insert(0, "/app")

# 在 import settings 之前覆盖环境变量
os.environ["TAVILY_KEY"] = "tvly-FAKE-KEY-TO-FORCE-FAILURE"

from app.db.base import SessionLocal
from app.models.project import NovelProject
from app.services.trend_service import execute_trend_exploration
from app.models.trend_exploration import TrendExploration

db = SessionLocal()
try:
    project = db.query(NovelProject).first()
    if project is None:
        print("没有可用项目")
        sys.exit(0)
    project_id = project.id
    print(f"使用 project_id={project_id}")

    # 清空已有 trend 让验证干净
    db.query(TrendExploration).filter(TrendExploration.project_id == project_id).delete()
    db.commit()
    print("已清空旧 trend_exploration")

    print("\n===== 开始执行热点探索（Tavily 必失败）=====")
    trend = execute_trend_exploration(
        db,
        project_id=project_id,
        title="验证：Tavily 失败时降级链路",
        query_text="修仙 小说 趋势",
        max_results=5,
    )
    print(f"\ntrend.id = {trend.id}")
    raw = json.loads(trend.raw_findings)
    print(f"raw_findings.source     = {raw.get('source')}")
    print(f"raw_findings.fallback   = {raw.get('fallback_chain')}")
    sources = raw.get("sources", [])
    print(f"topics 数 = {len(sources)}")
    for i, s in enumerate(sources[:3]):
        print(f"  [{i}] {s.get('title', '?')[:60]}")

    tags = json.loads(trend.extracted_tags) if trend.extracted_tags else []
    print(f"tags 数 = {len(tags)}")

    if raw.get("source") in ("duckduckgo", "firecrawl"):
        print(f"\n✅ 降级成功：Tavily 失败 → 自动用了 {raw.get('source')}")
    elif raw.get("source") == "fallback":
        chain = raw.get("fallback_chain", [])
        print(f"\n✅ 降级成功：3 路全失败 → 离线兜底 (chain={chain})")
    else:
        print(f"\n⚠️ 实际来源: {raw.get('source')}（chain={raw.get('fallback_chain')}）")
finally:
    db.close()
