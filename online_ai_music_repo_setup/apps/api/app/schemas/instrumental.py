from pydantic import BaseModel, Field


class InstrumentalGenerationRequest(BaseModel):
    sample_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=50)
    prompt: str = Field(min_length=1, max_length=1000)
    # Stable Audio Open's release generates clips up to ~47 seconds;
    # longer isn't supported by the model itself.
    duration_seconds: float = Field(default=30.0, gt=0, le=47.0)
    seed: int | None = None
