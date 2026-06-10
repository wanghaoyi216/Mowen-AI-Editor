"""验证 chat_completion 在 NVIDIA 模型上 max_tokens 正确扩展到 reasoning_budget + output。"""
import time
from app.integrations.openrouter_client import build_openrouter_client

client = build_openrouter_client()

print('=== Test: chat_completion with reasoning_budget + max_tokens ===')
t0 = time.time()
try:
    result = client.chat_completion(
        model='nvidia/nemotron-3-ultra-550b-a55b',
        system_prompt='你是一个简洁的中文助手。',
        user_prompt='用 JSON 格式输出你的名字和一句话自我介绍。格式：{"name": "...", "intro": "..."}',
    )
    elapsed = time.time() - t0
    print(f'STATUS: OK (elapsed {elapsed:.1f}s)')
    print(f'content: {result.get("content", "")[:500]}')
    print(f'model returned: {result.get("model")}')
except Exception as e:
    elapsed = time.time() - t0
    print(f'ERR ({elapsed:.1f}s): {type(e).__name__}: {str(e)[:300]}')
