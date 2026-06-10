from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NovelProject(Base):
    __tablename__ = "novel_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # ── 多用户隔离：owner_id 必填（NOT NULL）。旧数据由启动迁移统一回填为 1。────
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目所属用户（外键 → users.id，删除用户时级联清理）",
    )
    # ── 历史字段：保留 user_id 以兼容旧调用点（与 owner_id 同步）。──────────────
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="历史字段，等同 owner_id；保留以兼容旧代码",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    writing_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 创作超参数：写作语言 + 单章字数区间 + 目标章节数。这些字段会被真正注入
    # 到 LLM 创作 prompt，并用于章节字数强制校验。
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh-CN")
    min_words_per_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    max_words_per_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=4000)
    target_chapters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_setting: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    # 用户指定的导出根目录；为空则使用后端默认 EXPORT_ROOT。
    # 推荐填写绝对路径（容器内或宿主机均可），如 /exports/我的小说/项目A。
    export_root_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
