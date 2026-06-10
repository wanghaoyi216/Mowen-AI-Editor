import pytest

from app.services import openrouter_service


class FallbackOpenRouterClient:
    def list_free_models(self) -> list[dict]:
        return [
            {"id": "qwen/qwen-test:free"},
            {"id": "deepseek/deepseek-test:free"},
            {"id": "mistral/mistral-test:free"},
        ]

    def chat_completion(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        assert system_prompt
        assert user_prompt
        if model == "qwen/qwen-test:free":
            raise RuntimeError("qwen unavailable")
        return {"choices": [{"message": {"content": f"ok from {model}"}}]}


class AlwaysFailOpenRouterClient:
    def list_free_models(self) -> list[dict]:
        return [
            {"id": "qwen/qwen-test:free"},
            {"id": "deepseek/deepseek-test:free"},
        ]

    def chat_completion(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        raise RuntimeError(f"{model} unavailable")


def test_generate_with_openrouter_fallback_switches_to_next_model(monkeypatch) -> None:
    monkeypatch.setattr(openrouter_service, "build_openrouter_client", lambda: FallbackOpenRouterClient())

    result = openrouter_service.generate_with_openrouter_fallback(
        system_prompt="system",
        user_prompt="user",
        preferred_keywords=["qwen", "deepseek"],
    )

    assert result["model"]["id"] == "deepseek/deepseek-test:free"
    assert result["fallback_used"] is True
    assert result["attempts"] == [
        {"model_id": "qwen/qwen-test:free", "status": "failed", "error": "qwen unavailable"},
        {"model_id": "deepseek/deepseek-test:free", "status": "success", "error": None},
    ]
    assert result["completion"]["choices"][0]["message"]["content"] == "ok from deepseek/deepseek-test:free"


def test_generate_with_openrouter_fallback_reports_all_failed_models(monkeypatch) -> None:
    monkeypatch.setattr(openrouter_service, "build_openrouter_client", lambda: AlwaysFailOpenRouterClient())

    with pytest.raises(ValueError) as exc_info:
        openrouter_service.generate_with_openrouter_fallback(
            system_prompt="system",
            user_prompt="user",
            preferred_keywords=["qwen", "deepseek"],
            max_model_attempts=2,
        )

    message = str(exc_info.value)
    assert "OpenRouter completion failed for all fallback models" in message
    assert "qwen/qwen-test:free" in message
    assert "deepseek/deepseek-test:free" in message
