"""测试 OpenRouter 服务的 OpenAI 格式 completion 解析兼容性。

OpenRouter 在不同模型 / 端点上可能返回两种形态：
- OpenAI 格式 dict：``{"choices": [{"message": {"content": "..."}}]}``
- 纯字符串：直接是模型输出

本文件覆盖 ``extract_message_content`` helper 的 4 种输入分支，
并用 mock 验证 ``generate_with_openrouter`` 入口对 dict / str 两种返回的兼容性。
"""

from __future__ import annotations

import pytest

from app.integrations import openrouter_client as openrouter_client_module
from app.services import openrouter_service
from app.services.openrouter_service import extract_message_content


# ---------------------------------------------------------------------------
# 通用 mock：绕过 rate_limiter 与 settings 校验，让测试不依赖 Redis / 配置
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_rate_limiter(monkeypatch):
    """rate_limiter.acquire() 会无重试连接 Redis，单测环境不可用时直接禁用。"""
    monkeypatch.setattr(openrouter_service.rate_limiter, "acquire", lambda: True)
    monkeypatch.setattr(
        openrouter_service.rate_limiter, "record_call", lambda *a, **kw: None
    )


# ---------------------------------------------------------------------------
# helper 函数：4 种输入分支
# ---------------------------------------------------------------------------

def test_extract_message_content_from_openai_dict():
    """OpenAI 风格 dict：应能正确提取 choices[0].message.content。"""
    completion = {
        "choices": [
            {
                "message": {
                    "content": '{"result": 42}',
                    "role": "assistant",
                }
            }
        ]
    }
    assert extract_message_content(completion) == '{"result": 42}'


def test_extract_message_content_from_plain_string():
    """纯字符串：原样返回。"""
    assert extract_message_content("plain text result") == "plain text result"


def test_extract_message_content_from_none_returns_empty_string():
    """None 输入：返回空字符串，不抛异常。"""
    assert extract_message_content(None) == ""


def test_extract_message_content_from_anomalous_dict_returns_empty_string():
    """异常 dict（无 choices / choices 为空 / message 缺失）：返回空字符串。"""
    # 无 choices 字段
    assert extract_message_content({}) == ""
    # choices 为空列表
    assert extract_message_content({"choices": []}) == ""
    # choices[0] 不是 dict
    assert extract_message_content({"choices": [None]}) == ""
    # message 字段缺失
    assert extract_message_content({"choices": [{}]}) == ""
    # message 不是 dict
    assert extract_message_content({"choices": [{"message": "raw"}]}) == ""
    # message 中无 content
    assert extract_message_content({"choices": [{"message": {}}]}) == ""


# ---------------------------------------------------------------------------
# 端到端：mock build_openrouter_client，验证 generate_with_openrouter 返回结构
# ---------------------------------------------------------------------------

class _OpenAIDictCompletionClient:
    """模拟 OpenRouter 返回 OpenAI 格式 dict 的客户端。"""

    def list_free_models(self) -> list[dict]:
        return [{"id": "mock/test-model:free", "name": "Mock Test Model"}]

    def chat_completion(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        # 真实 OpenRouter chat_completion 返回的是 OpenAI 格式 dict
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"result": 42}',
                        "role": "assistant",
                    }
                }
            ],
            "model": model,
        }


class _StringCompletionClient:
    """模拟 OpenRouter 返回纯字符串 completion 字段的客户端。"""

    def list_free_models(self) -> list[dict]:
        return [{"id": "mock/string-model:free", "name": "Mock String Model"}]

    def chat_completion(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        # 某些 provider / 模型可能直接返回字符串
        return "plain text response"


def test_generate_with_openrouter_returns_openai_format_dict_completion(monkeypatch):
    """openrouter 返回的 completion 字段是 OpenAI 格式 dict（choices[0].message.content）。"""
    monkeypatch.setattr(
        openrouter_service,
        "build_openrouter_client",
        lambda: _OpenAIDictCompletionClient(),
    )
    # 同时把 integrations 模块里的名字也 patch（generate_with_openrouter_fallback
    # 通过 ``from app.integrations.openrouter_client import build_openrouter_client``
    # 拿到的引用会被 monkeypatch 自动覆盖，因为两个名字指向同一函数对象）。
    monkeypatch.setattr(
        openrouter_client_module,
        "build_openrouter_client",
        lambda: _OpenAIDictCompletionClient(),
    )

    result = openrouter_service.generate_with_openrouter(
        system_prompt="x",
        user_prompt="y",
    )

    completion = result["completion"]
    assert isinstance(completion, dict), "completion 应该是 OpenAI 格式 dict"
    assert "choices" in completion
    assert completion["choices"][0]["message"]["content"] == '{"result": 42}'

    # 兼容性：上层通过 helper 提取文本也工作
    assert extract_message_content(completion) == '{"result": 42}'


def test_generate_with_openrouter_fallback_handles_string_completion(monkeypatch):
    """当 completion 是纯字符串时，调用方应能正确处理（不崩溃、文本可提取）。"""
    monkeypatch.setattr(
        openrouter_service,
        "build_openrouter_client",
        lambda: _StringCompletionClient(),
    )
    monkeypatch.setattr(
        openrouter_client_module,
        "build_openrouter_client",
        lambda: _StringCompletionClient(),
    )

    result = openrouter_service.generate_with_openrouter(
        system_prompt="x",
        user_prompt="y",
    )

    completion = result["completion"]
    # helper 在 string 分支直接原样返回
    assert extract_message_content(completion) == "plain text response"
