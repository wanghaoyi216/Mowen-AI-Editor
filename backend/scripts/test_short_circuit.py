"""端到端测试：验证主模型短路 + fallback 自动切换。"""
import time
from app.services.openrouter_service import generate_with_openrouter_fallback

print('=== Test: streaming + first-byte short-circuit ===')
t0 = time.time()
deltas = []

def on_delta(text: str) -> None:
    deltas.append(text)
    print(f'  [delta {len(deltas)}] {text[:60]!r}')

try:
    result = generate_with_openrouter_fallback(
        system_prompt='你是一个简洁的中文助手。',
        user_prompt='用一句话回复我：你好',
        stream=True,
        on_delta=on_delta,
        max_model_attempts=3,
    )
    elapsed = time.time() - t0
    print(f'\n=== Result ===')
    print(f'  Total elapsed: {elapsed:.1f}s')
    print(f'  Successful model: {result["model"]["id"]}')
    print(f'  Fallback used: {result["fallback_used"]}')
    print(f'  Attempts: {len(result["attempts"])}')
    for a in result['attempts']:
        print(f'    - {a["model_id"]}: {a["status"]} {a.get("error", "")}')
    completion = result['completion']
    if isinstance(completion, dict):
        content = completion.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f'  Content ({len(content)} chars): {content[:200]}')
    print(f'  Deltas received: {len(deltas)}')
except Exception as e:
    elapsed = time.time() - t0
    print(f'\n=== FAILED after {elapsed:.1f}s ===')
    print(f'  ERR: {type(e).__name__}: {e}')
