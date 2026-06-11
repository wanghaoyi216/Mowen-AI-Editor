import logging
import time
from typing import Callable

from app.core.config import settings
from app.integrations.openrouter_client import AI_MODEL_RATE_LIMIT_MESSAGE, AI_SERVICE_UNAVAILABLE_MESSAGE
from app.integrations.openrouter_client import FirstByteTimeout, OpenRouterAPIError
from app.integrations.openrouter_client import build_openrouter_client
from app.services.rate_limiter import rate_limiter


logger = logging.getLogger(__name__)
# 模型 ID 必须与 NVIDIA NIM 端点（integrate.api.nvidia.com/v1）匹配
# 已用 /v1/models 接口验证：以下 ID 全部存在
NVIDIA_WRITING_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NVIDIA_SUBAGENT_MODEL = "minimaxai/minimax-m2.7"
DEFAULT_MODEL_KEYWORDS = ["nemotron", "minimax", "llama", "mistral", "qwen", "deepseek", "gemma", "moonshot"]
# 稳定且免费/可用的 fallback 模型 ID（NVIDIA NIM 端点）
STABLE_FREE_MODEL_IDS = [
    NVIDIA_WRITING_MODEL,
    NVIDIA_SUBAGENT_MODEL,
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "meta/llama-3.1-8b-instruct",
]
_last_successful_model_id: str | None = None


def _estimate_tokens(prompt: str, response: object) -> int:
    """粗略估算 token 数：1 token ≈ 4 字符（兼容中英文混排）。"""
    response_text = ""
    if isinstance(response, str):
        response_text = response
    elif isinstance(response, dict):
        try:
            choices = response.get("choices") or []
            if choices and isinstance(choices, list):
                message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                response_text = str(message.get("content", "") or "")
        except Exception:
            response_text = str(response)
    else:
        response_text = str(response)
    return max(0, len(prompt) // 4 + len(response_text) // 4)


def get_openrouter_free_models() -> dict:
    client = build_openrouter_client()
    if client is None:
        raise ValueError(AI_SERVICE_UNAVAILABLE_MESSAGE)

    try:
        free_models = client.list_free_models()
        selected = client.choose_free_model()
    except Exception as exc:
        raise ValueError(f"OpenRouter model discovery failed: {exc}") from exc
    return {
        "selected_model": selected,
        "free_models": free_models,
    }


def resolve_temperature(role: str | None, temperature: float | None) -> float | None:
    """根据 role 解析温度。

    - 显式传入 ``temperature`` 时优先生效。
    - ``role="creator"`` → 用 ``settings.creator_temperature``（更发散，利于创作）。
    - ``role="controller"`` → 用 ``settings.controller_temperature``（更收敛，利于审校/结构化输出）。
    - 其它情况返回 None（交由下游使用其默认温度）。
    """
    if temperature is not None:
        return temperature
    if role == "creator":
        return settings.creator_temperature
    if role == "controller":
        return settings.controller_temperature
    return None


def _optional_completion_kwargs(temperature: float | None, max_tokens: int | None) -> dict:
    """只在显式提供时才下传 temperature / max_tokens。

    这样默认调用方（temperature=None）不会给 client 传额外 kwargs，
    既兼容测试桩的固定签名，也保证生产端能按需覆盖温度与 max_tokens。
    """
    kwargs: dict = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return kwargs


def generate_with_openrouter(
    system_prompt: str,
    user_prompt: str,
    preferred_keywords: list[str] | None = None,
    stream: bool = False,
    on_delta: Callable[[str], None] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    role: str | None = None,
) -> dict:
    return generate_with_openrouter_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        preferred_keywords=preferred_keywords,
        max_model_attempts=8,
        stream=stream,
        on_delta=on_delta,
        temperature=resolve_temperature(role, temperature),
        max_tokens=max_tokens,
        role=role,
    )


def _ordered_model_candidates(
    models: list[dict],
    preferred_keywords: list[str] | None = None,
    max_model_attempts: int = 8,
) -> list[dict]:
    preferred_keywords = preferred_keywords or DEFAULT_MODEL_KEYWORDS
    configured_model_ids = [settings.creator_model, settings.controller_model]
    indexed = {model.get("id"): model for model in models if model.get("id")}

    configured: list[dict] = []
    for model_id in configured_model_ids:
        if model_id in indexed:
            configured.append(indexed[model_id])

    recently_successful: list[dict] = []
    if _last_successful_model_id and _last_successful_model_id in indexed:
        recently_successful.append(indexed[_last_successful_model_id])

    stable_free: list[dict] = []
    for model_id in STABLE_FREE_MODEL_IDS:
        if model_id in indexed:
            stable_free.append(indexed[model_id])

    prioritized: list[dict] = []
    fallback: list[dict] = []
    for model in models:
        model_id = (model.get("id") or "").lower()
        if any(keyword.lower() in model_id for keyword in preferred_keywords):
            prioritized.append(model)
        else:
            fallback.append(model)

    candidates: list[dict] = []
    seen: set[str] = set()
    for model in recently_successful + stable_free + prioritized + configured + fallback:
        model_id = model.get("id")
        if not model_id or model_id in seen:
            continue
        candidates.append(model)
        seen.add(model_id)
        if len(candidates) >= max(1, max_model_attempts):
            break
    return candidates


def _model_candidates_for_nvidia(client, max_model_attempts: int, role: str | None = None) -> list[str]:
    # 按角色决定首选模型：
    #   - controller（子 Agent：规划/审稿/一致性/场景拆解）→ 优先 MiniMax M2.7
    #   - creator（写正文）/ 默认 → 优先长上下文 Nemotron
    # 然后再串联另一个模型与 fallback 链，保证任一模型不可用时仍可降级。
    if role == "controller":
        configured = [
            model_id
            for model_id in [settings.controller_model, settings.creator_model, settings.nvidia_primary_model]
            if model_id
        ]
    else:
        configured = [
            model_id
            for model_id in [settings.creator_model, settings.controller_model, settings.nvidia_primary_model]
            if model_id
        ]
    fallback_configured = [
        model_id.strip()
        for model_id in settings.nvidia_fallback_models.split(",")
        if model_id.strip()
    ]
    discovered: list[str] = []
    prefer_discovered = False
    try:
        if hasattr(client, "list_models"):
            payload = client.list_models()
            items = payload.get("data", []) if isinstance(payload, dict) else []
        elif hasattr(client, "list_free_models"):
            items = client.list_free_models()
            prefer_discovered = True
        else:
            items = []
        models = [item for item in items if isinstance(item, dict) and item.get("id")]
        ordered = _ordered_model_candidates(models, DEFAULT_MODEL_KEYWORDS, max_model_attempts=max_model_attempts)
        discovered = [item["id"] for item in ordered if item.get("id")]
    except Exception as exc:
        logger.warning("NVIDIA API model discovery skipped: %s", exc)

    candidates: list[str] = []
    seen: set[str] = set()
    ordered_ids = (discovered + configured + fallback_configured) if prefer_discovered else (configured + fallback_configured + discovered)
    for model_id in ordered_ids:
        if model_id in seen:
            continue
        candidates.append(model_id)
        seen.add(model_id)
        if len(candidates) >= max(1, max_model_attempts):
            break
    return candidates


def _describe_model_error(client, exc: Exception) -> dict:
    if hasattr(client, "describe_model_error"):
        return client.describe_model_error(exc)
    return {}


def generate_with_openrouter_fallback(
    system_prompt: str,
    user_prompt: str,
    preferred_keywords: list[str] | None = None,
    max_model_attempts: int = 3,
    stream: bool = False,
    on_delta: Callable[[str], None] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    role: str | None = None,
) -> dict:
    """调用 OpenRouter 兼容 API 的统一入口，支持流式 + 多模型 fallback。

    参数：
        system_prompt: 系统提示
        user_prompt:  用户提示
        preferred_keywords: 优先模型关键字列表（与 free 模式相关）
        max_model_attempts: 最多尝试的模型数量
        stream: 是否走流式（OpenAI 风格 SSE）路径
        on_delta: 流式模式下每段增量文本的回调；为 None 时不推送
                  （流式路径会校验：传 stream=True 必须提供 on_delta）
    """
    # 流式模式必须提供回调
    if stream and on_delta is None:
        raise ValueError("stream=True requires on_delta callback to be provided")

    extra_kwargs = _optional_completion_kwargs(temperature, max_tokens)

    global _last_successful_model_id
    client = build_openrouter_client()
    if client is None:
        # 真正穷尽兜底（连 NVIDIA NIM 公开端点都不可用）。仍要 raise，但 message 友好
        raise ValueError(
            "无法创建 AI 客户端：NVIDIA_API_KEY 未配置且 NVIDIA NIM 公开端点也未启用。"
            "请在 .env 中设置 NVIDIA_API_KEY 或检查网络连通性。"
        )

    is_nvidia = "nvidia" in settings.nvidia_base_url.lower()
    if is_nvidia:
        candidate_models = _model_candidates_for_nvidia(client, max_model_attempts, role=role)
        if not candidate_models:
            raise ValueError("NVIDIA API: 未配置模型名称，请在 config 中设置 creator_model 和 controller_model")

        attempts: list[dict] = []
        last_error: Exception | None = None
        for idx, model_id in enumerate(candidate_models):
            # 短路策略：主模型（candidate[0]）只试 1 次，立刻切 fallback
            is_primary = idx == 0
            # 主模型：try_acquire 失败直接跳到 fallback，不阻塞
            # fallback：用阻塞 acquire（fallback 通常不消耗太多 token）
            acquired = False
            if is_primary:
                acquired = rate_limiter.try_acquire()
                if not acquired:
                    logger.warning(
                        "Rate limit exhausted (%d/%d), short-circuiting primary model %s",
                        rate_limiter.get_stats().get("total_calls", 0),
                        40,
                        model_id,
                    )
                    attempts.append({
                        "model_id": model_id,
                        "status": "skipped",
                        "error": "rate_limit_exhausted",
                    })
                    continue
            else:
                rate_limiter.acquire()
                acquired = True

            call_start = time.perf_counter()
            try:
                logger.info(
                    "NVIDIA API direct call: model=%s, prompt_length=%s, stream=%s, role=%s",
                    model_id,
                    len(system_prompt + user_prompt),
                    stream,
                    "primary" if is_primary else "fallback",
                )
                if stream:
                    # 主模型流式无首字节即短路切 fallback。timeout 暴露到 .env，
                    # NVIDIA 高峰期/限流时可调小（默认 10s 主、20s fallback）。
                    fb_timeout = (
                        float(settings.nvidia_primary_first_byte_timeout_seconds)
                        if is_primary
                        else float(settings.nvidia_fallback_first_byte_timeout_seconds)
                    )
                    # 主模型是 reasoning model，thinking 阶段可能 1-5 分钟
                    # fallback 是普通模型，几十秒足够
                    req_timeout = (
                        float(settings.nvidia_primary_request_timeout_seconds)
                        if is_primary
                        else float(settings.nvidia_fallback_request_timeout_seconds)
                    )
                    completion = client.chat_completion_stream(
                        model=model_id,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        on_delta=on_delta,
                        first_byte_timeout=fb_timeout,
                        request_timeout=req_timeout,
                        **extra_kwargs,
                    )
                else:
                    completion = client.chat_completion(
                        model=model_id,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        **extra_kwargs,
                    )
                attempts.append({"model_id": model_id, "status": "success", "error": None})
                _last_successful_model_id = model_id
                latency_ms = int((time.perf_counter() - call_start) * 1000)
                tokens = _estimate_tokens(system_prompt + user_prompt, completion)
                rate_limiter.record_call(model_id, tokens, latency_ms, success=True)
                return {
                    "model": {"id": model_id},
                    "completion": completion,
                    "attempts": attempts,
                    "fallback_used": len(attempts) > 1,
                }
            except Exception as exc:
                error_info = _describe_model_error(client, exc)
                status_code = error_info.get("status_code")
                is_first_byte_timeout = isinstance(exc, FirstByteTimeout)
                # 模型不存在 / 端点未挂载（404）→ 不要再重试这个 model，立即切下一个
                is_model_not_found = (
                    status_code in (400, 404)
                    and "model" in str(exc).lower()
                )
                logger.warning(
                    "NVIDIA API model failed: model=%s, role=%s, status=%s, first_byte_timeout=%s, "
                    "model_not_found=%s, error=%s",
                    model_id,
                    "primary" if is_primary else "fallback",
                    status_code,
                    is_first_byte_timeout,
                    is_model_not_found,
                    exc,
                )
                latency_ms = int((time.perf_counter() - call_start) * 1000)
                rate_limiter.record_call(model_id, 0, latency_ms, success=False)
                # 失败时释放 token，让下一个候选能立即尝试
                if acquired:
                    rate_limiter.release()
                    acquired = False
                last_error = exc
                attempt_info = {
                    "model_id": model_id,
                    "status": "failed",
                    "error": str(exc),
                    **error_info,
                }
                if is_first_byte_timeout:
                    attempt_info["first_byte_timeout"] = True
                if is_model_not_found:
                    attempt_info["model_not_found"] = True
                attempts.append(attempt_info)
                # 主模型首字节超时 → 不再重试主模型，直接走下一个 fallback
                if is_primary and is_first_byte_timeout:
                    logger.info(
                        "Primary model %s first-byte timeout, skipping to next fallback",
                        model_id,
                    )
                    continue
                # 模型不存在 → 立即跳到下一个候选
                if is_model_not_found:
                    logger.info(
                        "Model %s not found on this endpoint, skipping to next fallback",
                        model_id,
                    )
                    continue

        if isinstance(last_error, OpenRouterAPIError) and last_error.status_code == 429:
            raise ValueError(AI_MODEL_RATE_LIMIT_MESSAGE) from last_error
        failed = ", ".join(f"{attempt['model_id']}: {attempt['error']}" for attempt in attempts)
        raise ValueError(f"OpenRouter completion failed for all fallback models: {failed}") from last_error

    try:
        models = client.list_free_models()
    except Exception as exc:
        raise ValueError(f"OpenRouter model discovery failed: {exc}") from exc
    if not models:
        raise ValueError("No free OpenRouter models available")

    candidates = _ordered_model_candidates(models, preferred_keywords, max_model_attempts)

    attempts: list[dict] = []
    last_error: Exception | None = None
    for model in candidates:
        model_id = model.get("id")
        call_start = time.perf_counter()
        try:
            if stream:
                completion = client.chat_completion_stream(
                    model=model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    on_delta=on_delta,
                    **extra_kwargs,
                )
            else:
                completion = client.chat_completion(
                    model=model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    **extra_kwargs,
                )
            attempts.append({"model_id": model_id, "status": "success", "error": None})
            _last_successful_model_id = model_id
            latency_ms = int((time.perf_counter() - call_start) * 1000)
            tokens = _estimate_tokens(system_prompt + user_prompt, completion)
            rate_limiter.record_call(model_id, tokens, latency_ms, success=True)
            return {
                "model": model,
                "completion": completion,
                "attempts": attempts,
                "fallback_used": len(attempts) > 1,
            }
        except Exception as exc:
            error_info = _describe_model_error(client, exc)
            status_code = error_info.get("status_code")
            is_rate_limit = bool(error_info.get("is_rate_limit"))
            log_level = logger.warning if is_rate_limit else logger.error
            log_level(
                "OpenRouter fallback model failed: model=%s, status=%s, error=%s",
                model_id,
                status_code,
                exc,
                exc_info=not is_rate_limit,
            )
            latency_ms = int((time.perf_counter() - call_start) * 1000)
            rate_limiter.record_call(model_id, 0, latency_ms, success=False)
            last_error = exc
            attempts.append({"model_id": model_id, "status": "failed", "error": str(exc), **error_info})

    if isinstance(last_error, OpenRouterAPIError) and last_error.status_code == 429:
        raise ValueError(AI_MODEL_RATE_LIMIT_MESSAGE) from last_error
    raise ValueError(AI_SERVICE_UNAVAILABLE_MESSAGE) from last_error


def extract_message_content(completion: dict | str | None) -> str:
    """从 OpenRouter 返回的 completion 字段中安全提取文本内容。

    OpenRouter 在不同模型 / 端点上可能返回两种形态：
    - OpenAI 风格 dict：``{"choices": [{"message": {"content": "..."}}]}``
    - 纯字符串：直接是模型输出文本

    该 helper 容错处理：None、空 dict、缺 choices、message 不是 dict 等情况，
    均返回空字符串而不是抛异常，便于上层解析失败时 fallback。
    """
    if completion is None:
        return ""
    if isinstance(completion, str):
        return completion
    if isinstance(completion, dict):
        choices = completion.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            if isinstance(message, dict):
                return str(message.get("content") or "")
    return ""
