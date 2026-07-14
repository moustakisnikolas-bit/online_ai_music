import uuid

from pydantic import BaseModel, Field


class MetadataGenerateRequest(BaseModel):
    source_title: str = Field(min_length=1, max_length=255)
    mode: str = Field(min_length=1, max_length=50)
    duration_seconds: int = Field(gt=0)
    context: str = Field(default="ambient", max_length=50)
    language: str = Field(default="en", min_length=2, max_length=10)
    frequency_hz: float | None = Field(default=None, gt=0, le=20000)
    texture_mode: str | None = Field(default=None, max_length=50)


class MetadataPackageResponse(BaseModel):
    title: str
    subtitle: str
    description: str
    keywords: list[str]
    category: str
    language: str
    compliance_note: str


class ReviewDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ReviewDecisionResponse(BaseModel):
    job_id: uuid.UUID
    review_status: str
    reason: str | None
