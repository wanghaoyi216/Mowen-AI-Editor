"""AI 多样性相关 Pydantic 模型"""

from pydantic import BaseModel, Field


class AntiRepetitionResult(BaseModel):
    is_repetitive: bool = Field(description="是否存在重复")
    max_similarity: float = Field(description="最高相似度")
    similar_contents: list[dict] = Field(default_factory=list, description="相似内容列表")
    suggestion: str = Field(default="", description="调整建议")


class ContentEmbeddingCreate(BaseModel):
    content_type: str = Field(description="内容类型：plot/character/style/dialogue")
    source_id: int | None = Field(default=None, description="关联的章节/角色 ID")
    content_summary: str | None = Field(default=None, description="内容摘要")
