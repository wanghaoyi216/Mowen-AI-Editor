from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentEmbedding(Base):
    __tablename__ = "content_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("novel_projects.id"))
    content_type: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[int | None] = mapped_column(nullable=True)
    # MySQL 不支持 pgvector 的 Vector 类型，改用 JSON 存储向量数组
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def set_embedding(self, value: list[float]) -> None:
        """设置 embedding 向量（list[float]）"""
        self.embedding = value

    def get_embedding(self) -> list[float]:
        """获取 embedding 向量，统一返回 list[float]，无值时返回空列表"""
        return self.embedding or []
