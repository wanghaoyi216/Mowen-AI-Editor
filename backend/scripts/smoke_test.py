"""Comprehensive end-to-end smoke test for the v2-overhaul.

Verifies:
1. OpenAPI path count
2. All data dimensions (chapters, worldbook, trends, characters, scenes)
3. Dashboard data
4. Story arc data
5. All 4 export formats
6. AI tasks endpoint

Run: python scripts/smoke_test.py
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"
PROJECT_ID = 1


def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data,
        headers={"Content-Type": "application/json"} if body else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def expect(label: str, ok: bool, detail: str = "") -> bool:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label}{('  — ' + detail) if detail else ''}")
    return ok


def main() -> int:
    fails = 0
    print("=" * 60)
    print(" v2-overhaul E2E smoke test")
    print("=" * 60)

    print("\n[1] OpenAPI 路由")
    code, body = request("GET", "/openapi.json")
    n = len(body["paths"]) if body else 0
    if not expect(f"openapi.json paths={n}", n >= 60, f"got {n}"): fails += 1

    print("\n[2] 项目数据维度")
    code, body = request("GET", f"/projects/{PROJECT_ID}/chapters")
    chapters = (body or {}).get("data") or []
    if not expect(f"chapters count", len(chapters) >= 5, f"got {len(chapters)}"): fails += 1

    code, body = request("GET", f"/projects/{PROJECT_ID}/worldbook")
    wb = (body or {}).get("data") or []
    if not expect(f"worldbook count", len(wb) >= 5, f"got {len(wb)}"): fails += 1

    code, body = request("GET", f"/projects/{PROJECT_ID}/trend-explorations")
    trends = (body or {}).get("data") or []
    if not expect(f"trend-explorations count", len(trends) >= 1, f"got {len(trends)}"): fails += 1

    code, body = request("GET", f"/projects/{PROJECT_ID}/characters")
    chars = (body or {}).get("data") or []
    if not expect(f"characters count", len(chars) >= 1, f"got {len(chars)}"): fails += 1

    print("\n[3] Dashboard 数据")
    code, body = request("GET", f"/projects/{PROJECT_ID}/dashboard")
    d = (body or {}).get("data") or {}
    kpi = d.get("kpi", {})
    if not expect("KPI completedChapters", kpi.get("completedChapters", 0) > 0, f"got {kpi.get('completedChapters')}"): fails += 1
    if not expect("KPI totalWords", kpi.get("totalWords", 0) > 0, f"got {kpi.get('totalWords')}"): fails += 1
    radar = d.get("consistencyRadar", {})
    if not expect("Radar dimensions", len([k for k, v in radar.items() if v > 0]) >= 3, f"got {len(radar)} dims"): fails += 1
    if not expect("Character freq", len(d.get("characterFreq", [])) >= 1, f"got {len(d.get('characterFreq', []))}"): fails += 1
    if not expect("Genre distribution", len(d.get("genreDistribution", [])) >= 1, f"got {len(d.get('genreDistribution', []))}"): fails += 1

    print("\n[4] Story Arc 数据")
    code, body = request("GET", f"/projects/{PROJECT_ID}/story-arc")
    sa = (body or {}).get("data") or {}
    if not expect("story-arc nodes", len(sa.get("nodes", [])) >= 3, f"got {len(sa.get('nodes', []))}"): fails += 1
    if not expect("story-arc edges", len(sa.get("edges", [])) >= 1, f"got {len(sa.get('edges', []))}"): fails += 1

    print("\n[5] 章节场景数据")
    if chapters:
        first_id = chapters[0]["id"]
        code, body = request("GET", f"/projects/{PROJECT_ID}/chapters/{first_id}/scenes")
        sc = (body or {}).get("data") or {}
        scenes = sc.get("scenes", [])
        if not expect(f"ch.1 scenes count", len(scenes) >= 1, f"got {len(scenes)}"): fails += 1
        if scenes:
            s = scenes[0]
            if not expect("scene.pov present", s.get("pov") is not None, f"got {s.get('pov')}"): fails += 1
            if not expect("scene.word_count > 0", (s.get("word_count") or 0) > 0, f"got {s.get('word_count')}"): fails += 1

    print("\n[6] 导出格式")
    for fmt in ("md", "docx", "pdf", "txt"):
        if not chapters:
            break
        cid = chapters[0]["id"]
        url = f"{BASE}/projects/{PROJECT_ID}/chapters/{cid}/export?format={fmt}"
        try:
            with urllib.request.urlopen(url) as r:
                size = len(r.read())
            if not expect(f"export {fmt}", size > 100, f"size={size} bytes"): fails += 1
        except Exception as e:
            if not expect(f"export {fmt}", False, str(e)[:60]): fails += 1

    print("\n[7] AI 任务接口")
    code, body = request("GET", f"/projects/{PROJECT_ID}/tasks")
    tasks = (body or {}).get("data") or []
    if not expect("tasks endpoint", code == 200 and len(tasks) >= 0, f"code={code} count={len(tasks)}"): fails += 1

    code, body = request("GET", f"/projects/{PROJECT_ID}/tasks/concurrency")
    c = (body or {}).get("data") or {}
    if not expect("concurrency endpoint", code == 200, f"code={code}"): fails += 1

    print("\n" + "=" * 60)
    if fails == 0:
        print(" ✅ 全部通过")
        return 0
    else:
        print(f" ❌ {fails} 项失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
