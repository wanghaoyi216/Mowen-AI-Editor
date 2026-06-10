from pydantic import BaseModel


class ChapterConsistencyRead(BaseModel):
    task_id: int
    model: str
    report: str
