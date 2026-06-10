"""快速验证 3 路搜索 + 离线兜底。"""
from app.integrations.duckduckgo_client import build_duckduckgo_client
from app.integrations.firecrawl_client import build_firecrawl_client
from app.integrations.tavily_client import build_tavily_client
from app.core.config import settings

print("===== client 可用性 =====")
print("Tavily  :", build_tavily_client() is not None)
print("Firecrawl:", build_firecrawl_client() is not None)
print("DuckDuckGo:", build_duckduckgo_client() is not None)

# 真实走一次：模拟 tavily 失败 → firecrawl 失败 → ddg 兜底
print("\n===== 验证 DuckDuckGo 公开搜索 =====")
ddg = build_duckduckgo_client()
resp = ddg.search("赛博朋克 修仙 小说趋势", max_results=5)
print("source:", resp.get("source"))
print("total:", len(resp.get("results", [])))
for i, r in enumerate(resp.get("results", [])[:3]):
    print(f"  [{i}] {r['title'][:60]}")
    print(f"       url={r['url'][:80]}")
    print(f"       snippet={r['content'][:80]}")

# 验证 firecrawl search
print("\n===== 验证 Firecrawl /v2/search =====")
fc = build_firecrawl_client()
if fc is not None:
    try:
        resp2 = fc.search("赛博修仙 题材", limit=3, lang="zh", country="CN")
        print("raw response keys:", list(resp2.keys())[:6])
        data = resp2.get("data") or resp2.get("web") or resp2.get("results") or []
        print("total:", len(data) if isinstance(data, list) else "N/A")
        for i, item in enumerate(data[:2] if isinstance(data, list) else []):
            if isinstance(item, dict):
                print(f"  [{i}] {item.get('title', '?')[:60]} | {item.get('url', '?')[:80]}")
    except Exception as exc:
        print("firecrawl search exc:", type(exc).__name__, exc)

# 验证 Tavily
print("\n===== 验证 Tavily =====")
tv = build_tavily_client()
if tv is not None:
    try:
        resp3 = tv.search("测试", max_results=2)
        rs = resp3.get("results", []) if isinstance(resp3, dict) else []
        print("Tavily results:", len(rs))
    except Exception as exc:
        print("Tavily exc:", type(exc).__name__, exc)
