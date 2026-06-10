from pydantic import BaseModel


class OpenRouterModelRead(BaseModel):
    id: str
    name: str | None = None
    context_length: int | None = None


class OpenRouterModelSelectionRead(BaseModel):
    selected_model: OpenRouterModelRead | None
    free_models: list[OpenRouterModelRead]
