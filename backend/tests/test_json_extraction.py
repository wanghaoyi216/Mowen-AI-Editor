"""测试 ``_extract_json_from_text`` 工具函数。

该函数负责从 LLM 返回的文本中提取 JSON 字典，覆盖以下 4 种典型输入：
- 纯 JSON 字符串
- Markdown 代码块包裹（``json ... ```）
- 文本 + JSON 块 + 文本
- 直接传入 dict（防御性）
- 非法 JSON（应抛 ValueError）
"""

from __future__ import annotations

import pytest

from app.services.novel_orchestrator_service import _extract_json_from_text


def test_extract_pure_json():
    """纯 JSON 字符串：直接解析返回。"""
    text = '{"title": "x", "chapters": [1, 2, 3]}'
    result = _extract_json_from_text(text)
    assert result["title"] == "x"
    assert result["chapters"] == [1, 2, 3]


def test_extract_json_in_code_block():
    """Markdown 代码块包裹：提取代码块内 JSON 解析。"""
    text = '```json\n{"title": "y", "chapters": [4, 5]}\n```'
    result = _extract_json_from_text(text)
    assert result["title"] == "y"
    assert result["chapters"] == [4, 5]


def test_extract_json_with_surrounding_text():
    """多余文本 + JSON 块：找到首 { 与末 } 之间内容并解析。"""
    text = '以下是结果：\n{"title": "z", "chapters": []}\n其他内容'
    result = _extract_json_from_text(text)
    assert result["title"] == "z"
    assert result["chapters"] == []


def test_extract_json_from_dict_returns_dict_directly():
    """防御性：传入 dict 应原样返回（已经是 JSON 形态）。"""
    d = {"title": "w"}
    result = _extract_json_from_text(d)
    assert result == d


def test_extract_json_raises_on_invalid():
    """非法 JSON 应抛 ValueError。"""
    with pytest.raises(ValueError):
        _extract_json_from_text("not json at all, no braces")
