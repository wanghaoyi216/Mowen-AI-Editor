from pydantic import BaseModel


class TrendAssetMappingRequest(BaseModel):
    trend_id: int
    create_plot_lines: bool = True
    create_character_candidates: bool = True
    create_worldbook_entries: bool = True
