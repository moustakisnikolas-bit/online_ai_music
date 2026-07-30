import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class YouTubeAuthorizationUrlResponse(BaseModel):
    authorization_url: str
    state: str


class YouTubeConnectionStatusResponse(BaseModel):
    connected: bool
    channel_id: str | None = None
    channel_title: str | None = None
    connected_at: datetime | None = None
    has_playlist_scope: bool = False


class YouTubeQuotaStatusResponse(BaseModel):
    units_used: int
    daily_budget: int
    remaining: int
    uploads_remaining_today: int
    resets_at: datetime


class YouTubeUploadRequest(BaseModel):
    audio_job_id: uuid.UUID
    video_filename: str = Field(min_length=1, max_length=255)
    # Optional: sets this as the video's custom thumbnail after upload via
    # thumbnails().set(). A thumbnail failure doesn't fail the whole
    # publish (see YouTubePublicationResponse.thumbnail_set).
    artwork_filename: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=500)
    category_id: str = Field(default="10", max_length=10)
    # Uploads default to private so a human can review on YouTube itself
    # before making a track public, consistent with the approval-before-
    # publish principle: this endpoint's own review-status gate governs
    # whether AION is allowed to upload at all, and privacy_status governs
    # what happens to visibility once it's there.
    privacy_status: str = Field(default="private", pattern="^(private|unlisted|public)$")


class YouTubePublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_job_id: uuid.UUID
    video_filename: str
    title: str
    status: str
    youtube_video_id: str | None
    youtube_url: str | None
    thumbnail_set: bool
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class InternetArchiveStatusResponse(BaseModel):
    configured: bool


class InternetArchiveUploadRequest(BaseModel):
    audio_job_id: uuid.UUID
    audio_filename: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    creator: str | None = Field(default=None, max_length=255)
    license_url: str | None = Field(default=None, max_length=500)


class InternetArchivePublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_job_id: uuid.UUID
    item_identifier: str
    audio_filename: str
    title: str
    status: str
    archive_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
