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
) -> object:
    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= retries:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.25)
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry wrapper failed without raising a concrete exception")
