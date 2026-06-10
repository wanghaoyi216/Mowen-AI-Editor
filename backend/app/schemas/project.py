from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    theme: str | None = Field(default=None, max_length=200)
    target_audience: str | None = Field(default=None, max_length=100)
    writing_style: str | None = Field(default=None, max_length=100)
    tone: str | None = Field(default=None, max_length=100)
    language: str = Field(default="zh-CN", max_length=20)
    min_words_per_chapter: int = Field(default=2000, ge=200, le=50000)
    max_words_per_chapter: int = Field(default=4000, ge=200, le=50000)
    target_chapters: int | None = Field(default=None, ge=1, le=2000)
    summary: str | None = None
    world_setting: str | None = None
    status: str = Field(default="draft", max_length=50)
    # 用户指定的导出根目录；为空时使用后端默认 EXPORT_ROOT。
    export_root_path: str | None = Field(default=None, max_length=500)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    theme: str | None = Field(default=None, max_length=200)
    target_audience: str | None = Field(default=None, max_length=100)
    writing_style: str | None = Field(default=None, max_length=100)
    tone: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=20)
    min_words_per_chapter: int | None = Field(default=None, ge=200, le=50000)
    max_words_per_chapter: int | None = Field(default=None, ge=200, le=50000)
    target_chapters: int | None = Field(default=None, ge=1, le=2000)
    summary: str | None = None
    world_setting: str | None = None
    status: str | None = Field(default=None, max_length=50)
    export_root_path: str | None = Field(default=None, max_length=500)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
