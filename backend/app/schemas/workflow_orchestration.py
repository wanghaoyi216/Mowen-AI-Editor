from pydantic import BaseModel, ConfigDict


class AutoNovelWorkflowRequest(BaseModel):
    title: str | None = None
    query_text: str | None = None
    source_scope: str = "web"
    search_depth: str = "advanced"
    max_results: int = 5
    chapter_id: int | None = None
    chapter_no: int = 1
    chapter_title: str | None = None
    chapter_summary: str | None = None
    chapter_objective: str | None = None
    chapter_conflict: str | None = None
    design_guidance: str | None = None
    style_hint: str | None = None
    revision_focus: str | None = None
    word_target: int = 1800
    novel_length: str = "ai_decided"  # short/medium/long/ai_decided
    book_id: int | None = None  # 创作所属 book（可选；None 时取项目默认书）


class WorkflowExecuteRequest(BaseModel):
    objective: str | None = None
    max_steps: int = 3
    workflow_execution_id: str | None = None
    hyperparameters: dict | None = None


class WorkflowStepDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_no: int
    name: str
    objective: str
    expected_output: str
    tool_hints: list[str] = []


class WorkflowDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_id: str
    name: str
    trigger: str
    description: str
    dependencies: list[str] = []
    output: str
    steps: list[WorkflowStepDefinitionRead]
