from pydantic import BaseModel, Field


class NaturalSoundSampleResponse(BaseModel):
    id: str
    label: str
    category: str
    filename: str
    license: str
    source_url: str | None
    attribution: str | None
    source_type: str
    available: bool


class FreesoundSearchResultItem(BaseModel):
    freesound_id: int
    name: str
    license: str
    preview_url: str
    username: str
    page_url: str


class FreesoundImportRequest(BaseModel):
    freesound_id: int
    sample_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=50)
