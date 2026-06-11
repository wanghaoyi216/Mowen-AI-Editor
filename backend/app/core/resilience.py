import random
import time
from collections.abc import Callable


def with_retries(
    operation: Callable[[], object],
    *,
    retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    no_retry_exceptions: tuple[type[BaseException], ...] = (),
) -> object:
    """带退避的重试包装。

    ``retry_exceptions``: 触发重试的异常类型
    ``no_retry_exceptions``: 即使在 ``retry_exceptions`` 里也**不**重试的异常类型
    （例如 ``FirstByteTimeout`` —— 同一个模型刚 first-byte 超时，重试 5 次也只会等
    5×60s；更高层有 fallback 机制，直接抛出让上层切下一个模型更快）。
    """
    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except no_retry_exceptions as exc:
            # 显式不重试：直接抛给上层走 fallback
            raise
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry wrapper failed without raising a concrete exception")
