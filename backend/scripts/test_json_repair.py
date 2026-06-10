"""验证 _extract_json_from_text 能 repair 被截断的 JSON（模拟 task 5 的真实场景）。"""
import sys
sys.path.insert(0, '/app')

from app.services.novel_orchestrator_service import _extract_json_from_text, _try_repair_truncated_json

# 模拟 task 5 实际收到的截断 JSON
truncated = '''{
  "title": "界·龙影双生",
  "genre": "玄幻",
  "target_chapters": 50,
  "total_estimated_words": 200000,
  "chapters": [
    {
      "chapter_no": 1,
      "title": "废柴少年",
      "theme": "世界观铺垫与主角现状",
      "word_target": 4000,
      "key_events": [
        "介绍全民超能力世界，能力等级划分",'''

# 也测一下 LLM 实际可能返回的其它格式
test_cases = [
    ('truncated mid-array', truncated),
    ('<think> wrap', '<think>让我想想...</think>\n```json\n{"title":"x","chapters":[{"n":1}]}\n```'),
    ('plain valid', '{"title": "test", "chapters": []}'),
    ('truncated at string', '{"key_events": ["one", "two'),
    ('truncated at object', '{"a":1,"b":{"c":2,"d":'),
]

for name, text in test_cases:
    print(f'=== {name} ===')
    print(f'  input length: {len(text)}')
    try:
        result = _extract_json_from_text(text)
        print(f'  ✅ parsed: {result}')
    except Exception as e:
        print(f'  ❌ failed: {e}')
    print()
