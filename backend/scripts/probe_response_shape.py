"""抓原始响应看 Nemotron reasoning 模式的 content 在哪个字段。"""
import os, json, time, httpx

url = os.environ['NVIDIA_BASE_URL'].rstrip('/') + '/chat/completions'
key = os.environ['NVIDIA_API_KEY']
headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}

body = {
    'model': 'nvidia/nemotron-3-ultra-550b-a55b',
    'messages': [
        {'role': 'system', 'content': '你是一个简洁的中文助手。'},
        {'role': 'user', 'content': '用一句话回答：你好'},
    ],
    'temperature': 1,
    'top_p': 0.95,
    'max_tokens': 4096,
    'reasoning_budget': 4096,
    'chat_template_kwargs': {'enable_thinking': True},
    'stream': False,
}

t0 = time.time()
r = httpx.post(url, headers=headers, json=body, timeout=300.0)
print(f'STATUS: {r.status_code} (elapsed {time.time()-t0:.1f}s)')

data = r.json()
# 打印所有 top-level keys
print('Top-level keys:', list(data.keys()))
print('Choices count:', len(data.get('choices', [])))
for i, c in enumerate(data.get('choices', [])):
    msg = c.get('message', {})
    print(f'Choice {i} keys:', list(c.keys()))
    print(f'Choice {i} message keys:', list(msg.keys()))
    for k, v in msg.items():
        preview = str(v)[:200] if v else '<<None/empty>>'
        print(f'  {k!r}: {preview}')

# 打印 usage
if 'usage' in data:
    print('Usage:', json.dumps(data['usage'], ensure_ascii=False, indent=2))

# 打印完整响应的 structure（值截断）
def truncate(obj, limit=200):
    if isinstance(obj, str):
        return obj[:limit] + '...' if len(obj) > limit else obj
    if isinstance(obj, dict):
        return {k: truncate(v, limit) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncate(x, limit) for x in obj[:3]]
    return obj

print('--- Full response (truncated) ---')
print(json.dumps(truncate(data, 400), ensure_ascii=False, indent=2))
