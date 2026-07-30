from pydantic import BaseModel, Field


class SecretUpsertRequest(BaseModel):
    value: str = Field(min_length=1)


class SecretStatusResponse(BaseModel):
    key: str
    configured: bool
    source: str


class SecretStatusListResponse(BaseModel):
    secrets: list[SecretStatusResponse]
