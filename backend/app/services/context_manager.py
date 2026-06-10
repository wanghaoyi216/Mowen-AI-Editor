import json
import time
from typing import Any

import structlog

from app.db.session import redis_client

logger = structlog.get_logger(__name__)


class AIContext管理器:
    """
    AI 上下文管理模块 —— 在有限的 Token 预算内，帮助 AI 快速拾起记忆。

    核心策略：
    1. 分层记忆 (Layered Memory): 将上下文分为「持久层 / 摘要层 / 活跃层」
       - 持久层 (Persistent Layer): 项目设定、世界观、角色档案（始终携带）
       - 摘要层 (Summary Layer): 已写章节的高层摘要（滚动窗口，压缩存储）
       - 活跃层 (Active Layer): 最近 N 章的详细内容（完整携带）

    2. 语义检索 (Semantic Retrieval): 利用向量数据库存储章节 embedding，
       在每次 AI 调用时检索 Top-K 最相关章节片段

    3. Token 预算控制 (Token Budget): 限制总 Token 用量，自动裁剪低优先级内容

    4. 记忆衰减 (Memory Decay): 较久远的章节逐步降权，仅保留关键事件摘要
    """

    MAX_CONTEXT_TOKENS = 32000
    PERSISTENT_LAYER_TOKENS = 3000
    SUMMARY_LAYER_TOKENS = 5000
    ACTIVE_LAYER_TOKENS = 10000
    RETRIEVAL_TOP_K = 5

    def __init__(self, project_id: int):
        self.project_id = project_id
        self._redis = redis_client
        self._context_cache_key = f"context:{project_id}:active"
        self._summary_cache_key = f"context:{project_id}:summary"
        self._token_usage_key = f"context:{project_id}:token_usage"

    async def build_context(
        self,
        project_config: dict[str, Any],
        recent_chapters: list[dict[str, Any]],
        all_chapter_summaries: list[dict[str, Any]],
        worldbook: list[dict[str, Any]] | None = None,
        characters: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        构建 AI 上下文提示，分层组装。
        """
        parts = []
        token_budget = self.MAX_CONTEXT_TOKENS

        # Layer 1: 持久层（项目设定 + 世界观 + 角色）
        persistent = self._build_persistent_layer(project_config, worldbook, characters)
        persistent_tokens = self._estimate_tokens(persistent)
        parts.append(persistent)
        token_budget -= persistent_tokens

        # Layer 2: 摘要层（已写章节的压缩摘要）
        if token_budget > self.SUMMARY_LAYER_TOKENS:
            summaries = self._build_summary_layer(all_chapter_summaries, token_budget)
            summary_tokens = self._estimate_tokens(summaries)
            if summaries:
                parts.append(summaries)
                token_budget -= summary_tokens

        # Layer 3: 活跃层（最近章节的详细内容）
        if token_budget > self.ACTIVE_LAYER_TOKENS:
            active = self._build_active_layer(recent_chapters, token_budget)
            active_tokens = self._estimate_tokens(active)
            if active:
                parts.append(active)
                token_budget -= active_tokens

        # 组装最终上下文
        context = "\n\n".join([p for p in parts if p])

        await self._cache_context(context)
        await self._record_token_usage(self._estimate_tokens(context))

        return context

    def _build_persistent_layer(
        self,
        project_config: dict[str, Any],
        worldbook: list[dict[str, Any]] | None = None,
        characters: list[dict[str, Any]] | None = None,
    ) -> str:
        """构建持久层：项目设定 + 世界观 + 角色档案"""
        parts = ["## 项目设定"]
        parts.append(f"- 名称: {project_config.get('name', '未知')}")
        parts.append(f"- 类型: {project_config.get('genre', '未知')}")
        parts.append(f"- 目标章节: {project_config.get('target_chapters', 20)}")
        parts.append(f"- 每章目标字数: {project_config.get('target_words_per_chapter', 2000)}")
        if project_config.get('description'):
            parts.append(f"- 简介: {project_config['description']}")

        if worldbook:
            parts.append("\n## 世界观设定")
            for entry in worldbook[:20]:
                parts.append(f"- [{entry.get('category', '通用')}] {entry.get('title', '')}: {entry.get('content', '')[:200]}")

        if characters:
            parts.append("\n## 角色档案")
            for char in characters[:15]:
                parts.append(f"- {char.get('name', '未知')}: {char.get('description', '')[:200]}")

        return "\n".join(parts)

    def _build_summary_layer(
        self,
        chapter_summaries: list[dict[str, Any]],
        token_budget: int,
    ) -> str:
        """构建摘要层：已写章节的压缩摘要（滚动窗口）"""
        if not chapter_summaries:
            return ""

        parts = ["## 章节摘要（历史记录）"]

        for chapter in chapter_summaries[-30:]:
            summary = chapter.get('summary', chapter.get('content', ''))
            if len(summary) > 300:
                summary = summary[:300] + "..."

            chapter_num = chapter.get('chapter_number', chapter.get('id', '?'))
            title = chapter.get('title', f'第{chapter_num}章')
            parts.append(f"### 第{chapter_num}章 {title}")
            parts.append(f"摘要: {summary}")

            if self._estimate_tokens("\n".join(parts)) > token_budget:
                parts.pop()
                parts.pop()
                break

        return "\n".join(parts)

    def _build_active_layer(
        self,
        recent_chapters: list[dict[str, Any]],
        token_budget: int,
    ) -> str:
        """构建活跃层：最近 N 章的详细内容（完整携带）"""
        if not recent_chapters:
            return ""

        parts = ["## 最近章节详细内容（参考上下文）"]

        for chapter in recent_chapters[-3:]:
            content = chapter.get('content', '')
            chapter_num = chapter.get('chapter_number', chapter.get('id', '?'))
            title = chapter.get('title', f'第{chapter_num}章')
            parts.append(f"### 第{chapter_num}章 {title}")
            parts.append(content)

            if self._estimate_tokens("\n".join(parts)) > token_budget:
                parts.pop()
                parts.pop()
                break

        return "\n".join(parts)

    async def _cache_context(self, context: str):
        """缓存构建好的上下文到 Redis（v2-overhaul：Redis 已下线，使用进程内 shim）"""
        try:
            await self._redis.asetex(
                self._context_cache_key,
                3600,
                context,
            )
        except Exception as e:
            logger.warning("Failed to cache context", error=str(e))

    async def _record_token_usage(self, tokens: int):
        """记录 Token 使用情况"""
        try:
            current = await self._redis.aget(self._token_usage_key)
            total = (int(current) if current else 0) + tokens
            await self._redis.asetex(
                self._token_usage_key,
                86400,
                str(total),
            )
        except Exception as e:
            logger.warning("Failed to record token usage", error=str(e))

    async def get_cached_context(self) -> str | None:
        """从缓存获取上下文"""
        try:
            cached = await self._redis.aget(self._context_cache_key)
            return cached if cached else None
        except Exception:
            return None

    async def get_token_usage(self) -> int:
        """获取当前 Token 使用总量"""
        try:
            current = await self._redis.aget(self._token_usage_key)
            return int(current) if current else 0
        except Exception:
            return 0

    async def clear_context(self):
        """清除缓存的上下文"""
        try:
            await self._redis.adelete(
                self._context_cache_key,
                self._summary_cache_key,
                self._token_usage_key,
            )
        except Exception as e:
            logger.warning("Failed to clear context", error=str(e))

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        估算 Token 数量（粗略估计）
        英文 ~4 chars/token，中文 ~1.5 chars/token
        使用保守估计：平均 2 chars/token
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    @staticmethod
    def truncate_to_token_limit(text: str, max_tokens: int) -> str:
        """
        将文本截断到指定 Token 限制
        """
        estimated_chars = max_tokens * 2
        if len(text) <= estimated_chars:
            return text
        truncated = text[:estimated_chars]
        last_period = truncated.rfind('。')
        last_newline = truncated.rfind('\n')
        cut_point = max(last_period, last_newline)
        if cut_point > estimated_chars * 0.7:
            return truncated[:cut_point + 1]
        return truncated + "..."


context_manager = AIContext管理器
