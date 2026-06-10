"""Degradation Service - 降级策略与退避管理

为小说生成流程提供分级降级与重试策略：
  NORMAL(0)   - 正常执行
  RETRY(1)    - 重试，使用标准流程
  SIMPLIFIED(2) - 简化流程（减少 LLM 调用，更简单的 prompt）
  SKIP(3)     - 跳过本章，继续下一章

每个章节最多重试 3 次，退避策略为指数退避 + 随机抖动。
"""

from __future__ import annotations

import logging
import random
import time
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class DegradationLevel(IntEnum):
    """降级级别。"""

    NORMAL = 0       # 正常执行
    RETRY = 1        # 重试
    SIMPLIFIED = 2   # 简化流程
    SKIP = 3         # 跳过


MAX_RETRIES_PER_CHAPTER = 3
MAX_BACKOFF_SECONDS = 120.0


class DegradationManager:
    """跟踪每个章节的失败次数并决定降级级别。

    状态转移：
        0 次失败 -> NORMAL
        1 次失败 -> RETRY
        2 次失败 -> SIMPLIFIED
        3 次失败 -> SKIP
    """

    def __init__(
        self,
        max_retries: int = MAX_RETRIES_PER_CHAPTER,
        max_backoff: float = MAX_BACKOFF_SECONDS,
    ) -> None:
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        # chapter_no -> {"failures": int, "errors": list[str], "last_error": str}
        self._chapter_state: dict[int, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def record_failure(self, chapter_no: int, error: str) -> None:
        """记录一次章节失败。"""
        state = self._chapter_state.setdefault(
            chapter_no,
            {"failures": 0, "errors": [], "last_error": ""},
        )
        state["failures"] += 1
        state["errors"].append(error)
        state["last_error"] = error
        logger.warning(
            "DegradationManager: chapter %d failure #%d: %s",
            chapter_no,
            state["failures"],
            error[:200],
        )

    def get_degradation_level(self, chapter_no: int) -> DegradationLevel:
        """根据失败次数返回当前降级级别。"""
        state = self._chapter_state.get(chapter_no)
        if state is None or state["failures"] == 0:
            return DegradationLevel.NORMAL

        failures = state["failures"]
        if failures >= self.max_retries:
            return DegradationLevel.SKIP
        if failures == 2:
            return DegradationLevel.SIMPLIFIED
        return DegradationLevel.RETRY

    def should_retry(self, chapter_no: int) -> bool:
        """判断是否应该继续重试（未达到最大重试次数）。"""
        state = self._chapter_state.get(chapter_no)
        if state is None:
            return True
        return state["failures"] < self.max_retries

    def get_backoff_delay(self, chapter_no: int) -> float:
        """计算指数退避 + 随机抖动延迟。

        公式：2^n + random(0, 2)，上限 max_backoff。
        n = failure_count - 1（首次失败时 n=0）
        """
        state = self._chapter_state.get(chapter_no)
        if state is None or state["failures"] == 0:
            return 0.0

        n = state["failures"] - 1
        base_delay = 2 ** n
        jitter = random.uniform(0, 2.0)
        delay = min(self.max_backoff, base_delay + jitter)
        return delay

    def reset_chapter(self, chapter_no: int) -> None:
        """在章节成功后重置状态。"""
        if chapter_no in self._chapter_state:
            del self._chapter_state[chapter_no]
            logger.info("DegradationManager: chapter %d state reset after success", chapter_no)

    def get_last_error(self, chapter_no: int) -> str:
        """获取章节最近一次的错误信息。"""
        state = self._chapter_state.get(chapter_no)
        if state is None:
            return ""
        return state.get("last_error", "")

    def get_failure_count(self, chapter_no: int) -> int:
        """获取章节的失败次数。"""
        state = self._chapter_state.get(chapter_no)
        if state is None:
            return 0
        return state["failures"]

    def get_summary(self) -> dict[str, Any]:
        """返回所有章节的降级状态摘要。"""
        return {
            str(ch_no): {
                "failures": state["failures"],
                "level": self.get_degradation_level(ch_no).name,
                "last_error": state["last_error"][:200],
            }
            for ch_no, state in self._chapter_state.items()
            if state["failures"] > 0
        }
