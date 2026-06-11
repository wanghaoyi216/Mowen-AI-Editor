import json
import random
import time
import logging
from typing import Callable, Optional

import httpx

from app.core.config import settings
from app.core.resilience import with_retries


logger = logging.getLogger(__name__)
AI_SERVICE_UNAVAILABLE_MESSAGE = "AI 模型服务暂时不可用，请检查 API Key 配置或稍后重试"
AI_MODEL_RATE_LIMIT_MESSAGE = "AI 模型服务限流，正在切换模型或稍后重试"


class FirstByteTimeout(httpx.TimeoutException):
    """首字节超时：流式调用已建立 TCP 连接但 N 秒内未收到任何 SSE 数据。

    用来短路 reasoning model：主模型如果卡在 thinking 阶段，10s 没动静就切 fallback。
    """
    def __init__(self, model: str, timeout_s: float):
        super().__init__(f"No first byte within {timeout_s:.1f}s for model={model}")
        self.model = model
        self.timeout_s = timeout_s


class OpenRouterAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body_snippet: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body_snippet = body_snippet


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self._base_url:
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "Novel AI Editor"
        return headers

    def list_models(self) -> dict:
        def operation() -> dict:
            response = httpx.get(
                f"{self._base_url}/models",
                headers=self._headers(),
                timeout=settings.external_request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()

        return with_retries(
            operation,
            retries=settings.external_request_retries,
            retry_exceptions=(httpx.HTTPError,),
        )

    def list_free_models(self) -> list[dict]:
        payload = self.list_models()
        items = payload.get("data", [])
        free_models = []
        for item in items:
            model_id = item.get("id", "")
            pricing = item.get("pricing", {}) or {}
            prompt_price = pricing.get("prompt")
            completion_price = pricing.get("completion")
            if model_id.endswith(":free") or (
                (prompt_price == "0" or prompt_price == 0) and (completion_price == "0" or completion_price == 0)
            ):
                free_models.append(item)
        if not free_models and items:
            logger.info("No pricing-based free models found; falling back to all available models")
            free_models = items
        return free_models

    def choose_free_model(self, preferred_keywords: list[str] | None = None) -> dict | None:
        models = self.list_free_models()
        if not models:
            return None
        preferred_keywords = preferred_keywords or ["qwen", "mistral", "llama", "gemini"]
        prioritized = []
        fallback = []
        for model in models:
            model_id = (model.get("id") or "").lower()
            if any(keyword in model_id for keyword in preferred_keywords):
                prioritized.append(model)
            else:
                fallback.append(model)
        pool = prioritized or fallback
        return random.choice(pool)

    @staticmethod
    def describe_model_error(exc: Exception) -> dict:
        status_code = exc.status_code if isinstance(exc, OpenRouterAPIError) else None
        return {
            "status_code": status_code,
            "message": str(exc),
            "is_rate_limit": status_code == 429,
        }

    def chat_completion(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        enable_thinking: bool | None = None,
        reasoning_budget: int | None = None,
        top_p: float | None = None,
    ) -> dict:
        prompt = f"{system_prompt}\n{user_prompt}"
        logger.info("Calling OpenRouter: model=%s, prompt_length=%s", model, len(prompt))

        # 读取默认（Nemotron reasoning 模型专用）参数
        if enable_thinking is None:
            enable_thinking = settings.nvidia_enable_thinking
        if reasoning_budget is None:
            reasoning_budget = settings.nvidia_reasoning_budget
        if top_p is None:
            top_p = settings.nvidia_top_p

        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        # NVIDIA Nemotron 模型：thinking 模式才传 reasoning_budget / chat_template_kwargs
        if model.startswith("nvidia/") and enable_thinking:
            payload["top_p"] = top_p
            payload["chat_template_kwargs"] = {"enable_thinking": True}
            payload["reasoning_budget"] = int(reasoning_budget)
            # max_tokens 必须 = reasoning_budget + output 预算，否则 thinking 阶段会
            # 耗光 token，output 阶段被截断。
            if max_tokens is None or max_tokens < int(reasoning_budget) + int(settings.nvidia_max_output_tokens):
                max_tokens = int(reasoning_budget) + int(settings.nvidia_max_output_tokens)
        elif model.startswith("nvidia/"):
            # 非 thinking 模式：直接出正文，仍传 top_p，但不传 reasoning 参数
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        def operation() -> dict:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=settings.llm_request_timeout_seconds,
            )
            if response.status_code >= 400:
                body_snippet = response.text[:500] if response.text else ""
                logger.warning(
                    "OpenRouter chat_completion HTTP error: model=%s, status=%s, body=%s",
                    model,
                    response.status_code,
                    body_snippet,
                )
                if response.status_code == 429:
                    raise OpenRouterAPIError(
                        AI_MODEL_RATE_LIMIT_MESSAGE,
                        status_code=response.status_code,
                        body_snippet=body_snippet,
                    )
                if response.status_code in (400, 404) and "model" in body_snippet.lower():
                    # 模型不存在 / 不可用 → 上层要快速跳过此 model，切换到下一个 fallback
                    raise OpenRouterAPIError(
                        f"Model {model!r} is not available on this endpoint (status={response.status_code})",
                        status_code=response.status_code,
                        body_snippet=body_snippet,
                    )
                raise OpenRouterAPIError(
                    AI_SERVICE_UNAVAILABLE_MESSAGE,
                    status_code=response.status_code,
                    body_snippet=body_snippet,
                )
            return response.json()

        try:
            result = with_retries(
                operation,
                retries=settings.external_request_retries,
                retry_exceptions=(httpx.TimeoutException, httpx.NetworkError),
            )
        except OpenRouterAPIError:
            raise
        except Exception as exc:
            logger.error("OpenRouter chat_completion failed: %s", exc, exc_info=True)
            raise RuntimeError(AI_SERVICE_UNAVAILABLE_MESSAGE) from exc

        choices = result.get("choices") if isinstance(result, dict) else None
        logger.info(
            "OpenRouter completed: model=%s, choices=%s",
            model,
            len(choices) if isinstance(choices, list) else 0,
        )
        return result

    def chat_completion_stream(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        on_delta: Callable[[str], None],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        enable_thinking: bool | None = None,
        reasoning_budget: int | None = None,
        top_p: float | None = None,
        first_byte_timeout: float | None = None,
        request_timeout: float | None = None,
    ) -> dict:
        """流式调用 OpenRouter 兼容 API，逐 chunk 回调 ``on_delta``。

        行为：
          1. 发送 ``stream=True`` 请求
          2. 逐行解析 SSE，``data: {...}`` 行中的 ``choices[0].delta.content``
             累加到内部缓冲区，并通过 ``on_delta`` 推给调用方
          3. ``data: [DONE]`` 出现后合并完整 content 并组装成与 ``chat_completion``
             相同结构的 dict 返回
          4. 任何 HTTP 4xx/5xx / 解析异常都包装为 ``OpenRouterAPIError``

        短路机制：
          - first_byte_timeout: 发出 POST 后到收到第一个非空 SSE 数据行的最大等待秒数
            超过则抛 ``FirstByteTimeout``，调用方可捕获并切 fallback
          - request_timeout: 整体请求超时（默认 settings.llm_request_timeout_seconds=300s）
        """
        if on_delta is None:
            raise ValueError("on_delta callback is required for streaming")

        prompt = f"{system_prompt}\n{user_prompt}"
        logger.info(
            "Calling OpenRouter (stream): model=%s, prompt_length=%s, first_byte_timeout=%s",
            model,
            len(prompt),
            first_byte_timeout,
        )

        # 读取默认（Nemotron reasoning 模型专用）参数
        if enable_thinking is None:
            enable_thinking = settings.nvidia_enable_thinking
        if reasoning_budget is None:
            reasoning_budget = settings.nvidia_reasoning_budget
        if top_p is None:
            top_p = settings.nvidia_top_p
        if request_timeout is None:
            request_timeout = float(settings.llm_request_timeout_seconds)

        url = f"{self._base_url}/chat/completions"
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if model.startswith("nvidia/") and enable_thinking:
            payload["top_p"] = top_p
            payload["chat_template_kwargs"] = {"enable_thinking": True}
            payload["reasoning_budget"] = int(reasoning_budget)
            if max_tokens is None or max_tokens < int(reasoning_budget) + int(settings.nvidia_max_output_tokens):
                max_tokens = int(reasoning_budget) + int(settings.nvidia_max_output_tokens)
                payload["max_tokens"] = max_tokens
        elif model.startswith("nvidia/"):
            payload["top_p"] = top_p
        headers = self._headers()
        headers["Accept"] = "text/event-stream"

        content_parts: list[str] = []
        role: str = "assistant"
        model_id_returned: str = model
        finish_reason: Optional[str] = None

        def operation() -> dict:
            nonlocal content_parts, role, model_id_returned, finish_reason
            content_parts = []
            role = "assistant"
            model_id_returned = model
            finish_reason = None

            with httpx.Client(timeout=request_timeout) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        # 读取 body 以便错误处理（必须在 stream 内）
                        body_snippet = response.read().decode("utf-8", errors="replace")[:500]
                        logger.warning(
                            "OpenRouter chat_completion_stream HTTP error: model=%s, status=%s, body=%s",
                            model,
                            response.status_code,
                            body_snippet,
                        )
                        if response.status_code == 429:
                            raise OpenRouterAPIError(
                                AI_MODEL_RATE_LIMIT_MESSAGE,
                                status_code=response.status_code,
                                body_snippet=body_snippet,
                            )
                        if response.status_code in (400, 404) and "model" in body_snippet.lower():
                            raise OpenRouterAPIError(
                                f"Model {model!r} is not available on this endpoint (status={response.status_code})",
                                status_code=response.status_code,
                                body_snippet=body_snippet,
                            )
                        raise OpenRouterAPIError(
                            AI_SERVICE_UNAVAILABLE_MESSAGE,
                            status_code=response.status_code,
                            body_snippet=body_snippet,
                        )

                    # 首字节计时器：发出请求后 N 秒内没收到任何 SSE 数据行 → 短路
                    request_start = time.monotonic()
                    first_byte_deadline = (
                        request_start + first_byte_timeout
                        if first_byte_timeout and first_byte_timeout > 0
                        else None
                    )
                    # 绝对 deadline：流开启后总耗时不能超过 request_timeout
                    # （httpx 的 timeout 是 per-read，遇到 keep-alive 注释行不触发，
                    # 没有 absolute deadline 的话 LLM 那边 hang 死会让我们永远阻塞）
                    absolute_deadline = (
                        request_start + request_timeout
                        if request_timeout and request_timeout > 0
                        else None
                    )
                    got_first_byte = False
                    saw_any_line = False

                    for raw_line in response.iter_lines():
                        # 绝对 deadline 短路：每行 read 前先检查，超过强制抛超时
                        # 这样无论服务端发什么（数据行 / keep-alive / 啥都不发）
                        # 都能在 deadline 时退出流（切 fallback）
                        if absolute_deadline is not None and time.monotonic() > absolute_deadline:
                            logger.warning(
                                "OpenRouter stream absolute deadline exceeded: model=%s, timeout=%.1fs",
                                model,
                                request_timeout,
                            )
                            raise FirstByteTimeout(model, request_timeout)
                        saw_any_line = True
                        # 首字节短路：未收到任何 data 行，且已超时
                        if not got_first_byte and first_byte_deadline is not None:
                            if time.monotonic() > first_byte_deadline:
                                logger.warning(
                                    "OpenRouter stream first-byte timeout: model=%s, timeout=%.1fs",
                                    model,
                                    first_byte_timeout,
                                )
                                raise FirstByteTimeout(model, first_byte_timeout)

                        if not raw_line:
                            continue
                        # SSE 规范允许 CRLF；去除末尾换行
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith(":"):
                            # 注释行（keep-alive 等）——不算 first byte
                            continue
                        if not line.startswith("data:"):
                            # 忽略非 data 行
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        # 收到第一个有效 data 行后关闭首字节计时
                        if not got_first_byte:
                            got_first_byte = True
                            first_byte_deadline = None
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            # 忽略无法解析的行
                            continue
                        if not isinstance(chunk, dict):
                            continue
                        # 记录 model id
                        if "model" in chunk and isinstance(chunk["model"], str):
                            model_id_returned = chunk["model"]
                        choices = chunk.get("choices") or []
                        if not isinstance(choices, list) or not choices:
                            continue
                        first = choices[0]
                        if not isinstance(first, dict):
                            continue
                        # finish_reason
                        if first.get("finish_reason") is not None:
                            finish_reason = first.get("finish_reason")
                        delta = first.get("delta") or {}
                        if not isinstance(delta, dict):
                            continue
                        if "role" in delta and isinstance(delta["role"], str):
                            role = delta["role"]
                        delta_content = delta.get("content")
                        if isinstance(delta_content, str) and delta_content:
                            content_parts.append(delta_content)
                            try:
                                on_delta(delta_content)
                            except Exception as cb_exc:  # noqa: BLE001 - 回调失败不能中断 LLM 流
                                logger.debug(
                                    "OpenRouter stream on_delta callback raised: %s",
                                    cb_exc,
                                )
                    # 流结束后再次检查首字节超时（流可能因 keep-alive 空行保持连接
                    # 而无 data 行，循环自然结束 —— 这种情况下不算 first byte timeout）
                    if not saw_any_line and first_byte_deadline is not None and time.monotonic() > first_byte_deadline:
                        raise FirstByteTimeout(model, first_byte_timeout)
            return {
                "model": model_id_returned,
                "role": role,
                "content": "".join(content_parts),
                "finish_reason": finish_reason,
            }

        try:
            assembled = with_retries(
                operation,
                retries=settings.external_request_retries,
                retry_exceptions=(httpx.TimeoutException, httpx.NetworkError),
            )
        except OpenRouterAPIError:
            raise
        except Exception as exc:
            logger.error(
                "OpenRouter chat_completion_stream failed: %s", exc, exc_info=True
            )
            raise RuntimeError(AI_SERVICE_UNAVAILABLE_MESSAGE) from exc

        full_content = assembled.get("content", "") or ""
        # 组装成与 chat_completion 兼容的 OpenAI 风格 dict
        completion = {
            "id": None,
            "object": "chat.completion",
            "model": assembled.get("model", model),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": assembled.get("role", "assistant"),
                        "content": full_content,
                    },
                    "finish_reason": assembled.get("finish_reason"),
                }
            ],
        }
        logger.info(
            "OpenRouter stream completed: model=%s, content_chars=%d",
            completion["model"],
            len(full_content),
        )
        return completion


def build_openrouter_client() -> OpenRouterClient | None:
    """构造 NVIDIA NIM（OpenAI 兼容协议）客户端，支持多端点兜底。

    优先级：
      1. 用户配置的 ``NVIDIA_API_KEY`` + ``NVIDIA_BASE_URL``（生产走 NVIDIA NIM）
      2. 用户只配 ``NVIDIA_API_KEY``、未配 base_url → 走 NVIDIA NIM 公共端点
      3. 完全没配 key → 仍然尝试 NVIDIA 公开免费端点（很多免费模型可匿名访问）
         —— 这样即使没配 key 也不会立刻让 workflow crash；调用失败再 raise。
    """
    api_key = settings.nvidia_api_key
    base_url = settings.nvidia_base_url or "https://openrouter.ai/api/v1"

    if api_key:
        logger.info(
            "OpenRouter client: using endpoint %s with configured API key (prefix=%s...)",
            base_url,
            api_key[:6],
        )
        return OpenRouterClient(api_key, base_url)

    # ── 兜底：没配 key → 用 OpenRouter 公共端点 + 占位 key ─────────────
    # 多数免费模型不需要 token，但 Authorization 头必须存在。
    placeholder_key = "sk-or-v1-public-fallback-no-key-configured"
    fallback_url = "https://openrouter.ai/api/v1"
    logger.warning(
        "NVIDIA_API_KEY is not configured; falling back to public NVIDIA NIM endpoint %s "
        "with a placeholder key. Some models may reject anonymous access. "
        "Please set NVIDIA_API_KEY for reliable inference.",
        fallback_url,
    )
    return OpenRouterClient(placeholder_key, fallback_url)
