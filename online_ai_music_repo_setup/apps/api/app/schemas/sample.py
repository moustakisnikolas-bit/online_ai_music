from pydantic import BaseModel


class NaturalSoundSampleResponse(BaseModel):
    id: str
    label: str
    category: str
    filename: str
    license: str
    source_url: str | None
    attribution: str | None
    available: bool
