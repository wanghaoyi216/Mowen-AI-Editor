"""AI 创作多样性引擎 - 确保内容复杂多变，避免千篇一律"""

import math
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class AIDiversityEngine:
    """AI 创作多样性引擎"""
    
    def __init__(self):
        self.nvidia_api_key = settings.nvidia_api_key
        self.base_url = "https://integrate.api.nvidia.com/v1"

    async def generate_embedding(self, text: str) -> list[float]:
        """使用 NVIDIA NIM Embedding 模型生成文本向量"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.nvidia_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://novel-ai-editor.local",
                    "X-Title": "Novel AI Editor",
                },
                json={
                    "model": settings.embedding_model,
                    "input": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    
    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    async def save_embedding(
        self,
        db: AsyncSession,
        project_id: int,
        content_type: str,
        embedding: list[float],
        source_id: Optional[int] = None,
        content_summary: Optional[str] = None,
    ) -> "ContentEmbedding":
        """保存向量到数据库"""
        from app.db.models import ContentEmbedding
        # MySQL 迁移：使用 helper 方法统一存/取 list[float]，避免依赖 pgvector
        record = ContentEmbedding(
            project_id=project_id,
            content_type=content_type,
            source_id=source_id,
            content_summary=content_summary,
        )
        if hasattr(record, "set_embedding"):
            record.set_embedding(embedding)
        else:
            record.embedding = embedding
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    
    async def search_similar(
        self,
        db: AsyncSession,
        project_id: int,
        embedding: list[float],
        content_type: str,
        top_k: int = 5,
        threshold: float = 0.75,
    ) -> list[dict]:
        """检索相似内容"""
        from app.db.models import ContentEmbedding
        result = await db.execute(
            select(ContentEmbedding).where(
                ContentEmbedding.project_id == project_id,
                ContentEmbedding.content_type == content_type,
            )
        )
        existing = result.scalars().all()
        
        similarities = []
        for record in existing:
            # MySQL 迁移：使用 helper 获取 list[float]，避免 pgvector 的 .tolist() 调用
            record_vec = record.get_embedding() if hasattr(record, "get_embedding") else record.embedding
            sim = self.cosine_similarity(embedding, record_vec or [])
            if sim >= threshold:
                similarities.append({
                    "id": record.id,
                    "source_id": record.source_id,
                    "content_summary": record.content_summary,
                    "similarity": sim,
                    "created_at": record.created_at,
                })
        
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_k]
    
    async def anti_repetition_check(
        self,
        db: AsyncSession,
        project_id: int,
        new_content: str,
        content_type: str,
        source_id: Optional[int] = None,
    ) -> dict:
        """
        反重复检测
        
        Returns:
            {
                "is_repetitive": bool,
                "max_similarity": float,
                "similar_contents": list,
                "suggestion": str
            }
        """
        embedding = await self.generate_embedding(new_content)
        similar = await self.search_similar(
            db, project_id, embedding, content_type,
            top_k=5, threshold=0.75,
        )
        
        if not similar:
            return {"is_repetitive": False, "max_similarity": 0.0, "similar_contents": [], "suggestion": ""}
        
        max_sim = max(c["similarity"] for c in similar)
        
        if max_sim > settings.similarity_threshold:
            most_similar = similar[0]
            return {
                "is_repetitive": True,
                "max_similarity": max_sim,
                "similar_contents": similar,
                "suggestion": f"检测到与第{most_similar['source_id']}章{content_type}相似度达{max_sim:.0%}，请创作不同的{content_type}",
            }
        
        return {"is_repetitive": False, "max_similarity": max_sim, "similar_contents": similar, "suggestion": ""}


# 单例
diversity_engine = AIDiversityEngine()
