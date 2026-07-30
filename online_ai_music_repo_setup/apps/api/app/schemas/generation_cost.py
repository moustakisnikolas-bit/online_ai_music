from pydantic import BaseModel


class GenerationCostSummary(BaseModel):
    total_usd: float
    by_kind_usd: dict[str, float]
    count_by_kind: dict[str, int]
