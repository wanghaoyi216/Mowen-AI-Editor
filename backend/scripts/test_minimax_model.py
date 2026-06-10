"""Verify the MiniMax M2.7 sub-agent model responds via the NVIDIA integrate API.

Run inside the backend container:
    docker exec novel-ai-editor-backend python scripts/test_minimax_model.py
"""
import json

import httpx

from app.core.config import settings


def main() -> None:
    url = f"{settings.nvidia_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    for model in [settings.creator_model, settings.controller_model]:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "用一句话自我介绍。"}],
            "max_tokens": 80,
            "temperature": 0.4,
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code >= 400:
                print(f"[FAIL] {model} -> {resp.status_code}: {resp.text[:300]}")
            else:
                content = (
                    resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                print(f"[OK]   {model} -> {content[:160]!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR]  {model} -> {exc}")


if __name__ == "__main__":
    main()
