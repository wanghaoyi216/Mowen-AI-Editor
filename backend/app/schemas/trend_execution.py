from pydantic import BaseModel


class TrendExecutionRequest(BaseModel):
    title: str
    query_text: str
    source_scope: str = "web"
    search_depth: str = "advanced"
    max_results: int = 5
