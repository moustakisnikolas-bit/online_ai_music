import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AlbumConceptResponse(BaseModel):
    id: str
    label: str
    purpose_id: str
    natural_sound_categories: list[str]
    texture_fallbacks: list[str]
    hz_pool: list[float]
    melody_instruments: list[str]
    melody_scales: list[str]
    noise_type_preference: list[str]
    # Was silently dropped by response_model filtering before this field
    # existed here -- list_concepts() always included it in the raw dict,
    # but AlbumConceptResponse's declared fields are what actually
    # reaches the client.
    brainwave_bands: list[str] = []


class ConceptResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept_id: str
    query: str
    sample_size: int
    # [[value, count], ...], most-to-least common -- real YouTube Data
    # API search results, not estimated.
    top_hz_values: list[list]
    top_noise_types: list[list]
    top_themes: list[list]
    top_duration_buckets: list[list]
    top_videos: list[dict]
    researched_at: datetime


class AlbumBatchCreateRequest(BaseModel):
    concept_id: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    seed: int | None = None


class AlbumTrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    album_batch_id: uuid.UUID
    sequence_index: int
    title: str
    status: str
    harmony_check_status: str
    harmony_check_attempts: int
    harmony_check_report: dict | None
    audio_job_id: uuid.UUID | None
    video_filename: str | None
    artwork_filename: str | None
    youtube_publication_id: uuid.UUID | None
    scheduled_upload_date: date | None
    uploaded_at: datetime | None
    playlist_item_status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AlbumBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    concept_id: str
    title: str
    status: str
    youtube_playlist_id: str | None
    youtube_playlist_url: str | None
    playlist_status: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    # Not a model column -- a computed status-count breakdown across the
    # batch's tracks, filled in by the route (see routes/albums.py).
    track_summary: dict[str, int] = Field(default_factory=dict)


class AlbumBatchDetailResponse(AlbumBatchResponse):
    tracks: list[AlbumTrackResponse] = Field(default_factory=list)


class AlbumTrackShortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    album_track_id: uuid.UUID
    clip_index: int
    start_offset_seconds: int
    duration_seconds: int
    status: str
    video_filename: str | None
    artwork_filename: str | None
    youtube_publication_id: uuid.UUID | None
    scheduled_upload_date: date | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    # Not model columns -- filled in by the route from the parent
    # AlbumTrack/YouTubePublication so the UI doesn't need a second
    # round-trip per short just to show what it's a clip of.
    track_title: str = ""
    concept_id: str = ""
    youtube_url: str | None = None


class AlbumTrackShortsListResponse(BaseModel):
    # Real counts by status -- e.g. {"pending": 3, "rendered": 1,
    # "uploaded": 12, "failed": 0} -- the "how many have been uploaded"
    # visibility the UI needs, computed from the same rows as `shorts`,
    # not estimated.
    summary: dict[str, int] = Field(default_factory=dict)
    shorts: list[AlbumTrackShortResponse] = Field(default_factory=list)
