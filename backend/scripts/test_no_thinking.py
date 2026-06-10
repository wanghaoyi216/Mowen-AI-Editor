"""验证 non-thinking 模式响应快 + content 字段正常。"""
import time, sys
sys.path.insert(0, '/app')
from app.integrations.openrouter_client import build_openrouter_client

client = build_openrouter_client()

print('=== Test: non-thinking mode, simple JSON prompt ===')
t0 = time.time()
deltas = []
def on_delta(text):
    deltas.append(text)
    if len(deltas) <= 5:
        print(f'  [delta {len(deltas)}] {text[:80]!r}')

try:
    result = client.chat_completion_stream(
        model='nvidia/nemotron-3-ultra-550b-a55b',
        system_prompt='你是中文助手。',
        user_prompt='用 JSON 输出你的名字和一句话介绍，格式：{"name": "x", "intro": "y"}',
        on_delta=on_delta,
        first_byte_timeout=15.0,
    )
    elapsed = time.time() - t0
    print(f'\n  Total: {elapsed:.1f}s, deltas: {len(deltas)}')
    print(f'  Content: {result.get("content", "")[:400]}')
    print(f'  Finish: {result.get("finish_reason")}')
    print(f'  Model returned: {result.get("model")}')
except Exception as e:
    elapsed = time.time() - t0
    print(f'\n  ERR ({elapsed:.1f}s): {type(e).__name__}: {str(e)[:300]}')
