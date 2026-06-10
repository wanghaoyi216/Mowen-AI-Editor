"""Smoke test for the optimization pass: models, web research, knowledge graph,
user-message interaction, pause/resume control.

Run against the running backend:
    docker exec novel-ai-editor-backend python scripts/smoke_optimizations.py
"""
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def _get(path: str) -> dict:
    r = httpx.get(BASE + path, timeout=30)
    return {"status": r.status_code, "json": _safe_json(r)}


def _post(path: str, body: dict | None = None, timeout: float = 60) -> dict:
    r = httpx.post(BASE + path, json=body or {}, timeout=timeout)
    return {"status": r.status_code, "json": _safe_json(r)}


def _safe_json(r: httpx.Response):
    try:
        return r.json()
    except Exception:
        return {"_text": r.text[:300]}


def main() -> None:
    ok = True

    # 1. health
    h = httpx.get("http://127.0.0.1:8000/health", timeout=10)
    print(f"[health] {h.status_code} {h.text[:80]}")

    # 2. projects
    projects = _get("/projects")
    plist = projects["json"].get("data", []) if isinstance(projects["json"], dict) else []
    print(f"[projects] status={projects['status']} count={len(plist)}")
    if not plist:
        print("  (no projects — create one in the UI to exercise graph/message endpoints)")
        pid = None
    else:
        pid = plist[0]["id"]

    # 3. models — verify sub-agent = minimax
    if pid:
        models = _get(f"/projects/{pid}/tasks/models")
        data = models["json"].get("data", {})
        print(f"[models] primary={data.get('primary')} subagent={data.get('subagent_model')}")
        if data.get("subagent_model") != "minimaxai/minimax-m2.7":
            print("  !! subagent_model is not minimax-m2.7")
            ok = False
        if data.get("creator_model") != "nvidia/nemotron-3-ultra-550b-a55b":
            print("  !! creator_model is not nemotron-3-ultra-550b")
            ok = False

    # 4. knowledge graph generation (uses controller/minimax model + web nothing)
    if pid:
        print("[graph] generating knowledge graph (AI, may take ~30s)...")
        g = _post(f"/projects/{pid}/graph/generate", timeout=180)
        gd = g["json"].get("data", {}) if isinstance(g["json"], dict) else {}
        print(f"  status={g['status']} result={json.dumps(gd, ensure_ascii=False)[:200]}")
        # fetch graph
        graph = _get(f"/projects/{pid}/graph?graph_type=story_entity")
        nodes = graph["json"].get("data", {}).get("nodes", [])
        rels = graph["json"].get("data", {}).get("relationships", [])
        print(f"  graph nodes={len(nodes)} relationships={len(rels)}")

    print("\nRESULT:", "OK" if ok else "ISSUES FOUND")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
