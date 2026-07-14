from pydantic import BaseModel, Field


class ArtworkGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(default="Original Ambient Audio", max_length=255)
    preset_name: str = Field(default="spotify-cover", max_length=100)
    seed: int = 42


class ArtworkGenerateResponse(BaseModel):
    filename: str
    file_path: str
    preset_name: str
    width: int
    height: int


class VideoManifestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(gt=0, le=28800)
    width: int = Field(default=1920, ge=320, le=7680)
    height: int = Field(default=1080, ge=240, le=4320)
    frame_rate: int = Field(default=30, ge=1, le=120)


class VideoManifestResponse(BaseModel):
    manifest_filename: str
    manifest_path: str
