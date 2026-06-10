from pydantic import BaseModel


class MinimalReActExecutionRequest(BaseModel):
    title: str
    module_type: str
    objective: str
    chapter_id: int | None = None
    plot_line_id: int | None = None
