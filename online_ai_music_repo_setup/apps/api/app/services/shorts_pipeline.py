import logging
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.audio.concepts import get_concept
from app.core.config import get_settings
from app.models.album import AlbumTrack
from app.models.album_track_short import AlbumTrackShort
from app.repositories.album_track_shorts import (
    create_album_track_short,
    list_actionable_track_shorts,
    list_tracks_needing_shorts,
    update_album_track_short,
)
from app.repositories.albums import get_album_batch
from app.repositories.audio_jobs import get_audio_job
from app.repositories.generation_costs import FLUX_REPLICATE, record_estimated_cost
from app.repositories.youtube import (
    create_youtube_publication,
    get_youtube_credential,
    mark_publication_failed,
    mark_publication_uploaded,
)
from app.repositories.youtube_quota import (
    record_quota_usage,
    remaining_quota_today,
    today_pacific,
)
from app.services.ai_artwork_generator import generate_ai_artwork
from app.services.album_pipeline import (
    ARTWORK_DIR,
    TRACK_DURATION_SECONDS,
    VIDEO_DIR,
    _combination_from_dict,
    _hashtags_from_title,
    _track_artwork_prompt,
)
from app.services.artwork_generator import PRESETS, composite_thumbnail_labels
from app.services.metadata_generator import compliance_note_for
from app.services.video_renderer import render_static_video
from app.services.youtube_publisher import credentials_from_stored, upload_video

logger = logging.getLogger(__name__)

# YouTube's own title limit -- a Shorts title is the base track title plus
# the " #Shorts" discovery-signal suffix, truncated to fit.
_YOUTUBE_TITLE_MAX_LENGTH = 100
_SHORTS_TITLE_SUFFIX = " #Shorts"


def _compute_start_offsets(clip_count: int, clip_duration_seconds: int) -> list[int]:
    # Spreads clip_count starts evenly across TRACK_DURATION_SECONDS, from
    # 0 up to the latest point a clip of this duration can still start
    # without running past the end of the source audio.
    if clip_count <= 0:
        return []

    latest_start = max(0, TRACK_DURATION_SECONDS - clip_duration_seconds)

    if clip_count == 1:
        return [0]

    step = latest_start / (clip_count - 1)
    return [int(round(step * index)) for index in range(clip_count)]


def _ensure_track_shorts(db: Session, track: AlbumTrack) -> list[AlbumTrackShort]:
    settings = get_settings()
    offsets = _compute_start_offsets(settings.shorts_per_track, settings.shorts_duration_seconds)

    return [
        create_album_track_short(
            db,
            album_track_id=track.id,
            clip_index=index,
            start_offset_seconds=offset,
            duration_seconds=settings.shorts_duration_seconds,
        )
        for index, offset in enumerate(offsets)
    ]


def _ensure_track_vertical_artwork(db: Session, track: AlbumTrack, batch) -> str:
    # One shared vertical image per track, reused by every one of its
    # shorts -- they differ only in audio offset, not visual subject, so
    # generating a separate AI photo per short would be pure waste
    # (shorts_per_track x the Replicate spend for zero benefit). Mirrors
    # album_pipeline._ensure_track_artwork exactly, just a different
    # filename/preset/directory-shared-with-long-form is fine since the
    # "-vertical" suffix can't collide with the long-form "track-{id}.png".
    concept = get_concept(batch.concept_id)
    combination = _combination_from_dict(track.combination)
    filename = f"track-{track.id}-vertical.png"
    target_path = ARTWORK_DIR / filename

    if target_path.exists():
        return filename

    preset = PRESETS["youtube-shorts"]
    result = generate_ai_artwork(
        _track_artwork_prompt(concept, combination),
        output_path=target_path,
        provider="replicate",
        width=preset.width,
        height=preset.height,
        seed=abs(hash(str(track.id))) % 65536,
        db=db,
    )

    record_estimated_cost(
        db,
        kind=FLUX_REPLICATE,
        estimate_usd=get_settings().flux_replicate_cost_usd,
        reference=filename,
    )

    if result.path != target_path:
        result.path.replace(target_path)

    composite_thumbnail_labels(
        target_path,
        headline=concept.label.upper(),
        subline=f"{combination.tone_hz:g} Hz",
    )

    return filename


def _run_short_render_stage(db: Session, short: AlbumTrackShort) -> None:
    settings = get_settings()
    track = db.get(AlbumTrack, short.album_track_id)
    batch = get_album_batch(db, track.album_batch_id)
    audio_job = get_audio_job(db, track.audio_job_id)
    audio_filename = Path(audio_job.output_file_path).name
    artwork_filename = _ensure_track_vertical_artwork(db, track, batch)
    output_filename = f"{short.id}.mp4"

    render_static_video(
        audio_dir=settings.audio_output_path,
        artwork_dir=ARTWORK_DIR,
        output_dir=VIDEO_DIR,
        audio_filename=audio_filename,
        artwork_filename=artwork_filename,
        output_filename=output_filename,
        width=settings.shorts_width,
        height=settings.shorts_height,
        audio_start_seconds=short.start_offset_seconds,
        audio_duration_seconds=short.duration_seconds,
    )

    update_album_track_short(
        db,
        short,
        status="rendered",
        video_filename=output_filename,
        artwork_filename=artwork_filename,
    )


def _short_upload_metadata(db: Session, *, concept, track: AlbumTrack) -> tuple[str, str, list[str]]:
    base_title = track.title
    if len(base_title) + len(_SHORTS_TITLE_SUFFIX) > _YOUTUBE_TITLE_MAX_LENGTH:
        base_title = base_title[: _YOUTUBE_TITLE_MAX_LENGTH - len(_SHORTS_TITLE_SUFFIX)].rstrip()
    title = f"{base_title}{_SHORTS_TITLE_SUFFIX}"

    hashtags = _hashtags_from_title(track.title)
    hashtag_words = [tag.lstrip("#") for tag in hashtags]
    hashtag_line = " ".join([*hashtags, "#Shorts"])

    description = (
        f"{concept.label} -- a clip from the full-length ambient track. "
        f"Full version on the channel.\n\n"
        f"{compliance_note_for(concept.id)}\n\n"
        f"{hashtag_line}"
    )

    tags = list(dict.fromkeys(["ambient", "soundscape", "shorts", concept.id, *hashtag_words]))
    return title, description, tags


def _run_short_upload_stage(db: Session, short: AlbumTrackShort) -> None:
    settings = get_settings()
    credential = get_youtube_credential(db)

    if credential is None:
        raise ValueError("No YouTube channel is connected.")

    remaining = remaining_quota_today(db, budget=settings.youtube_daily_quota_budget)
    required = settings.youtube_upload_quota_cost_units + settings.youtube_quota_safety_margin_units

    if remaining < required:
        # Same "defer to Pacific tomorrow, re-checked live on every future
        # tick" pattern as _run_upload_stage in album_pipeline.py.
        update_album_track_short(
            db, short, scheduled_upload_date=today_pacific() + timedelta(days=1)
        )
        return

    track = db.get(AlbumTrack, short.album_track_id)
    batch = get_album_batch(db, track.album_batch_id)
    concept = get_concept(batch.concept_id)
    video_path = (VIDEO_DIR / short.video_filename).resolve()

    publication = create_youtube_publication(
        db,
        audio_job_id=track.audio_job_id,
        video_filename=short.video_filename,
        title=track.title,
        video_kind="short",
    )

    title, description, tags = _short_upload_metadata(db, concept=concept, track=track)

    try:
        credentials = credentials_from_stored(credential, db=db)
        video_id, video_url = upload_video(
            credentials,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id="10",
            privacy_status=settings.shorts_privacy_status,
        )
    except Exception as exc:
        mark_publication_failed(db, publication, error_message=str(exc))
        raise

    record_quota_usage(db, units=settings.youtube_upload_quota_cost_units)
    publication = mark_publication_uploaded(
        db, publication, youtube_video_id=video_id, youtube_url=video_url
    )

    update_album_track_short(db, short, status="uploaded", youtube_publication_id=publication.id)


def _advance_short(db: Session, short: AlbumTrackShort) -> None:
    try:
        if short.status == "pending":
            _run_short_render_stage(db, short)
        elif short.status == "rendered":
            _run_short_upload_stage(db, short)
    except Exception as exc:
        logger.exception("Album track short %s failed at status %r", short.id, short.status)
        update_album_track_short(db, short, status="failed", error_message=str(exc))


def run_shorts_worker_tick(db: Session, *, today: date | None = None) -> None:
    """One unit of work per call, mirroring album_pipeline.run_album_worker_tick:
    either spawn one confirmed-uploaded track's shorts, or advance one
    existing short by one stage. A complete no-op while shorts_enabled is
    False, so wiring this into the worker loop is always safe regardless
    of the flag's value.
    """
    settings = get_settings()

    if not settings.shorts_enabled:
        return

    if today is None:
        today = today_pacific()

    backfill_cutoff_date: date | None = None
    if settings.shorts_backfill_cutoff_date:
        backfill_cutoff_date = date.fromisoformat(settings.shorts_backfill_cutoff_date)

    needing_shorts = list_tracks_needing_shorts(
        db, limit=1, backfill_cutoff_date=backfill_cutoff_date
    )

    if needing_shorts:
        _ensure_track_shorts(db, needing_shorts[0])
        return

    actionable_shorts = list_actionable_track_shorts(db, limit=1, today=today)

    if not actionable_shorts:
        return

    _advance_short(db, actionable_shorts[0])
