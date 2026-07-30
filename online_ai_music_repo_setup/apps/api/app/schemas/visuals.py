from typing import Literal

from pydantic import BaseModel, Field


class ArtworkGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(default="Original Ambient Audio", max_length=255)
    preset_name: str = Field(default="spotify-cover", max_length=100)
    seed: int = 42
    # "procedural" (default) keeps the existing gradient-and-text renderer,
    # unchanged, so existing callers see no behavior change. "replicate"
    # and "openrouter" route to a real AI image model instead -- openrouter
    # is wired up but intentionally left unconfigured (no API key) until
    # it's needed, see ai_artwork_generator.py.
    provider: Literal["procedural", "replicate", "openrouter"] = "procedural"
    style_prompt: str | None = Field(default=None, max_length=2000)


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


class VideoRenderRequest(BaseModel):
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str = Field(min_length=1, max_length=500)
    output_filename: str = Field(min_length=1, max_length=500)
    width: int = Field(default=1920, ge=320, le=7680)
    height: int = Field(default=1080, ge=240, le=4320)
    frame_rate: int = Field(default=30, ge=1, le=120)


class VideoRenderResponse(BaseModel):
    filename: str
    file_path: str


class ExportBundleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str | None = Field(default=None, max_length=500)
    video_filename: str | None = Field(default=None, max_length=500)
    caption_filename: str | None = Field(default=None, max_length=500)
    metadata: dict


class ExportBundleResponse(BaseModel):
    manifest_filename: str
    manifest_path: str
    zip_filename: str
    zip_path: str


class RenderedVideoResponse(BaseModel):
    filename: str
    size_bytes: int
    modified_at: str
