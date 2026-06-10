from datetime import datetime

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """单个生成文件的元信息"""

    path: str = Field(description="文件相对路径")
    name: str = Field(description="文件名")
    size: int = Field(description="文件大小（字节）")
    modified_at: datetime = Field(description="最后修改时间")
    file_type: str = Field(description="文件类型: chapter, asset, log, archive")


class FileList(BaseModel):
    """文件列表响应"""

    files: list[FileInfo] = Field(description="文件列表")
    total: int = Field(description="文件总数")


class FileContent(BaseModel):
    """文件内容响应"""

    path: str = Field(description="文件相对路径")
    content: str = Field(description="文件内容（文本格式）")
    metadata: dict = Field(default_factory=dict, description="文件元数据")


class FileUpdateRequest(BaseModel):
    """文件更新请求体"""

    content: str = Field(description="新的文件内容")
    comment: str | None = Field(default=None, description="更新备注")
