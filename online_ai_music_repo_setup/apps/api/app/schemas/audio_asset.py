from pydantic import BaseModel, Field


class AudioAssetMetadataResponse(BaseModel):
    filename: str
    file_size_bytes: int = Field(ge=0)
    checksum_sha256: str
    channels: int = Field(ge=1)
    sample_rate: int = Field(gt=0)
    sample_width_bytes: int = Field(gt=0)
    frame_count: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    download_url: str
