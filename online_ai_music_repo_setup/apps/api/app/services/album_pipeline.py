import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.audio.concepts import get_concept
from app.audio.purposes import get_purpose
from app.audio.types import AudioMode, ChannelMode, TextureMode
from app.audio.validation import check_combination_harmony
from app.core.config import get_settings
from app.models.album import AlbumBatch, AlbumTrack
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubePublication
from app.repositories.albums import (
    TERMINAL_BATCH_STATUSES,
    TERMINAL_TRACK_STATUSES,
    create_album_batch as _insert_album_batch,
    create_album_track,
    get_album_batch,
    list_actionable_tracks,
    list_album_tracks,
    update_album_batch,
    update_album_track,
)
from app.repositories.audio_jobs import get_audio_job
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
from app.schemas.audio import AudioGenerationRequest
from app.services.album_combinations import (
    NaturalSoundChoice,
    TrackCombination,
    generate_candidate_combinations,
    render_harmony_preview,
    safe_fallback_combination,
)
from app.services.artwork_generator import generate_artwork
from app.services.audio_generator import generate_audio
from app.services.video_renderer import render_static_video
from app.services.youtube_publisher import (
    add_video_to_playlist,
    create_playlist,
    credentials_from_stored,
    upload_video,
)

logger = logging.getLogger(__name__)

# Real album tracks; harmony-check previews are short and cheap, gated
# separately by album_combinations._PREVIEW_DURATION_SECONDS.
TRACK_DURATION_SECONDS = 3600
MAX_HARMONY_ATTEMPTS = 3

VIDEO_DIR = Path("data/generated/video")
ARTWORK_DIR = Path("data/generated/artwork")
# Harmony-check preview renders never get published or downloaded --
# separate directory so they don't clutter the real audio library.
PREVIEW_DIR = Path("data/generated/album_previews")


# --- Combination <-> JSON round-trip ---------------------------------

def _combination_to_dict(combination: TrackCombination) -> dict:
    return {
        "natural_sound_kind": combination.natural_sound.kind,
        "natural_sound_sample_id": combination.natural_sound.sample_id,
        "natural_sound_texture_type": (
            combination.natural_sound.texture_type.value
            if combination.natural_sound.texture_type is not None
            else None
        ),
        "natural_sound_gain": combination.natural_sound_gain,
        "melody_instrument": combination.melody_instrument,
        "melody_scale": combination.melody_scale,
        "melody_root_note": combination.melody_root_note,
        "melody_gain": combination.melody_gain,
        "tone_hz": combination.tone_hz,
        "tone_gain": combination.tone_gain,
        "noise_type": combination.noise_type.value,
        "noise_gain": combination.noise_gain,
    }


def _combination_from_dict(data: dict) -> TrackCombination:
    natural_sound = NaturalSoundChoice(
        kind=data["natural_sound_kind"],
        sample_id=data["natural_sound_sample_id"],
        texture_type=(
            TextureMode(data["natural_sound_texture_type"])
            if data["natural_sound_texture_type"] is not None
            else None
        ),
    )
    return TrackCombination(
        natural_sound=natural_sound,
        natural_sound_gain=data["natural_sound_gain"],
        melody_instrument=data["melody_instrument"],
        melody_scale=data["melody_scale"],
        melody_root_note=data["melody_root_note"],
        melody_gain=data["melody_gain"],
        tone_hz=data["tone_hz"],
        tone_gain=data["tone_gain"],
        noise_type=AudioMode(data["noise_type"]),
        noise_gain=data["noise_gain"],
    )


# --- Batch creation -----------------------------------------------------

def create_album_batch(
    db: Session,
    *,
    concept_id: str,
    title: str | None = None,
    seed: int | None = None,
) -> AlbumBatch:
    concept = get_concept(concept_id)  # raises ValueError for an unknown concept
    batch_title = title or f"{concept.label} — Album {uuid.uuid4().hex[:6]}"

    batch = _insert_album_batch(db, concept_id=concept_id, title=batch_title)

    combinations = generate_candidate_combinations(concept_id, count=10, seed=seed)
    # A too-small real+fallback pool could return fewer than 10 unique
    # combinations -- pad with the safe fallback rather than short an
    # album, since the fallback is guaranteed valid.
    while len(combinations) < 10:
        combinations.append(safe_fallback_combination(concept_id))

    for index, combination in enumerate(combinations):
        create_album_track(
            db,
            album_batch_id=batch.id,
            sequence_index=index,
            title=f"{batch_title} - Track {index + 1}",
            combination=_combination_to_dict(combination),
        )

    return update_album_batch(db, batch, status="generating")


# --- Per-stage pipeline functions ---------------------------------------

def _run_harmony_check_stage(db: Session, track: AlbumTrack) -> None:
    batch = get_album_batch(db, track.album_batch_id)
    concept = get_concept(batch.concept_id)
    combination = _combination_from_dict(track.combination)
    attempts = track.harmony_check_attempts
    tried_signatures = {combination.signature()}
    report = None

    while True:
        samples, sample_rate = render_harmony_preview(combination, concept, PREVIEW_DIR)
        report = check_combination_harmony(
            samples,
            sample_rate,
            tone_frequency_hz=combination.tone_hz,
            melody_root_note_hz=combination.melody_root_note_hz(),
        )

        if report.passed:
            update_album_track(
                db,
                track,
                status="harmony_passed",
                harmony_check_status="passed",
                harmony_check_attempts=attempts,
                harmony_check_report={"issues": report.issues, "metrics": report.metrics},
                combination=_combination_to_dict(combination),
            )
            return

        attempts += 1

        if attempts >= MAX_HARMONY_ATTEMPTS:
            break

        replacement_seed = (hash((str(track.id), attempts)) & 0xFFFFFFFF)
        replacements = generate_candidate_combinations(
            batch.concept_id,
            count=1,
            seed=replacement_seed,
            exclude_signatures=frozenset(tried_signatures),
        )

        if not replacements:
            break

        combination = replacements[0]
        tried_signatures.add(combination.signature())

    # Exhausted real attempts (or the pool) without a pass -- fall back to
    # the pre-vetted, guaranteed-safe combination for this concept, marked
    # honestly rather than hidden.
    fallback = safe_fallback_combination(batch.concept_id)
    update_album_track(
        db,
        track,
        status="harmony_passed",
        harmony_check_status="passed_fallback",
        harmony_check_attempts=attempts,
        harmony_check_report={"issues": report.issues, "metrics": report.metrics} if report else None,
        combination=_combination_to_dict(fallback),
    )


def _run_full_render_stage(db: Session, track: AlbumTrack) -> None:
    batch = get_album_batch(db, track.album_batch_id)
    concept = get_concept(batch.concept_id)
    purpose = get_purpose(concept.purpose_id)
    combination = _combination_from_dict(track.combination)
    settings = get_settings()

    request = AudioGenerationRequest(
        title=track.title,
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        ambient_layers=combination.to_ambient_layers(),
        duration_seconds=TRACK_DURATION_SECONDS,
        sample_rate=44100,
        fade_in_seconds=5,
        fade_out_seconds=10,
        target_lufs=purpose.target_lufs,
        true_peak_dbtp=purpose.true_peak_dbtp,
        apply_mastering_eq=True,
        energy_start=purpose.energy_start,
        energy_middle=purpose.energy_middle,
        energy_end=purpose.energy_end,
    )

    result = generate_audio(request, settings.audio_output_path)

    audio_job = AudioJob(
        title=track.title,
        mode="mixed_ambient",
        channels="stereo",
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        amplitude=request.amplitude,
        status="completed",
        output_file_path=result.file_path,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        # The album pipeline's own harmony/quality gate is this content's
        # approval step -- there's no separate human review in the loop
        # for auto-generated album tracks.
        review_status="approved",
        review_reason="Auto-approved: passed the album pipeline's harmony/quality gate.",
        loudness_lufs=result.loudness_lufs,
        validation_warnings=result.validation_warnings,
    )
    db.add(audio_job)
    db.commit()
    db.refresh(audio_job)

    update_album_track(db, track, status="audio_rendered", audio_job_id=audio_job.id)


def _ensure_concept_artwork(concept_id: str) -> str:
    # One shared, procedural (free, instant) artwork per concept, cached
    # to disk -- not per-track, which would multiply a real cost (or at
    # minimum real render time) by 10 for no real benefit, since all 10
    # tracks in an album are the same concept.
    concept = get_concept(concept_id)
    filename = f"album-{concept_id}.png"
    target_path = ARTWORK_DIR / filename

    if target_path.exists():
        return filename

    generated_path = generate_artwork(
        title=concept.label,
        subtitle="AION Album",
        preset_name="youtube-thumbnail",
        output_dir=ARTWORK_DIR,
        seed=abs(hash(concept_id)) % 65536,
    )

    if generated_path != target_path:
        generated_path.replace(target_path)

    return filename


def _run_video_render_stage(db: Session, track: AlbumTrack) -> None:
    audio_job = get_audio_job(db, track.audio_job_id)
    audio_filename = Path(audio_job.output_file_path).name
    batch = get_album_batch(db, track.album_batch_id)
    artwork_filename = _ensure_concept_artwork(batch.concept_id)
    output_filename = f"{track.id}.mp4"

    render_static_video(
        audio_dir=get_settings().audio_output_path,
        artwork_dir=ARTWORK_DIR,
        output_dir=VIDEO_DIR,
        audio_filename=audio_filename,
        artwork_filename=artwork_filename,
        output_filename=output_filename,
    )

    update_album_track(
        db,
        track,
        status="video_rendered",
        video_filename=output_filename,
        artwork_filename=artwork_filename,
    )


def _run_upload_stage(db: Session, track: AlbumTrack) -> None:
    settings = get_settings()
    credential = get_youtube_credential(db)

    if credential is None:
        raise ValueError("No YouTube channel is connected.")

    remaining = remaining_quota_today(db, budget=settings.youtube_daily_quota_budget)
    required = settings.youtube_upload_quota_cost_units + settings.youtube_quota_safety_margin_units

    if remaining < required:
        # Not enough quota today -- defer to Pacific tomorrow. Re-checked
        # live (not gated on this field) on every future tick, so this is
        # informational for the UI rather than a hard scheduling lock.
        update_album_track(db, track, scheduled_upload_date=today_pacific() + timedelta(days=1))
        return

    batch = get_album_batch(db, track.album_batch_id)
    concept = get_concept(batch.concept_id)
    video_path = (VIDEO_DIR / track.video_filename).resolve()

    publication = create_youtube_publication(
        db,
        audio_job_id=track.audio_job_id,
        video_filename=track.video_filename,
        title=track.title,
    )

    try:
        credentials = credentials_from_stored(credential, db=db)
        video_id, video_url = upload_video(
            credentials,
            video_path=video_path,
            title=track.title,
            description=(
                f"Part of the {batch.title} album -- {concept.label} ambient soundscape, "
                "generated by AION."
            ),
            tags=["ambient", "soundscape", concept.id],
            category_id="10",
            privacy_status="private",
        )
    except Exception as exc:
        mark_publication_failed(db, publication, error_message=str(exc))
        raise

    record_quota_usage(db, units=settings.youtube_upload_quota_cost_units)
    publication = mark_publication_uploaded(
        db, publication, youtube_video_id=video_id, youtube_url=video_url
    )

    update_album_track(
        db,
        track,
        status="uploaded",
        youtube_publication_id=publication.id,
        uploaded_at=datetime.now(timezone.utc),
    )


def _run_playlist_stage(db: Session, track: AlbumTrack) -> None:
    settings = get_settings()
    batch = get_album_batch(db, track.album_batch_id)
    credential = get_youtube_credential(db)

    if credential is None:
        raise ValueError("No YouTube channel is connected.")

    credentials = credentials_from_stored(credential, db=db)

    if batch.youtube_playlist_id is None:
        concept = get_concept(batch.concept_id)
        playlist_id, playlist_url = create_playlist(
            credentials,
            title=batch.title,
            description=f"{concept.label} -- 10 ambient soundscapes generated by AION.",
        )
        record_quota_usage(db, units=settings.youtube_playlist_write_cost_units)
        batch = update_album_batch(
            db,
            batch,
            youtube_playlist_id=playlist_id,
            youtube_playlist_url=playlist_url,
            playlist_status="created",
        )

    publication = db.get(YouTubePublication, track.youtube_publication_id)

    if publication is None or publication.youtube_video_id is None:
        raise ValueError("Track has no uploaded YouTube video to add to the playlist.")

    try:
        add_video_to_playlist(
            credentials, playlist_id=batch.youtube_playlist_id, video_id=publication.youtube_video_id
        )
    except Exception as exc:
        update_album_track(db, track, playlist_item_status="failed", error_message=str(exc))
        raise

    record_quota_usage(db, units=settings.youtube_playlist_write_cost_units)
    update_album_track(db, track, status="playlist_added", playlist_item_status="added")


# --- Tick / state machine driver -----------------------------------------

def _advance_track(db: Session, track: AlbumTrack) -> None:
    try:
        if track.status == "pending":
            _run_harmony_check_stage(db, track)
        elif track.status == "harmony_passed":
            _run_full_render_stage(db, track)
        elif track.status == "audio_rendered":
            _run_video_render_stage(db, track)
        elif track.status == "video_rendered":
            _run_upload_stage(db, track)
        elif track.status == "uploaded":
            _run_playlist_stage(db, track)
    except Exception as exc:
        logger.exception("Album track %s failed at status %r", track.id, track.status)
        update_album_track(db, track, status="failed", error_message=str(exc))

    batch = get_album_batch(db, track.album_batch_id)
    if batch is not None:
        _finalize_batch_status_if_done(db, batch)


def _finalize_batch_status_if_done(db: Session, batch: AlbumBatch) -> None:
    if batch.status in TERMINAL_BATCH_STATUSES:
        return

    tracks = list_album_tracks(db, batch.id)

    if not tracks:
        return

    if any(track.status in {"video_rendered", "uploaded", "playlist_added"} for track in tracks):
        if batch.status == "generating":
            update_album_batch(db, batch, status="uploading")

    if any(track.status not in TERMINAL_TRACK_STATUSES for track in tracks):
        return

    if any(track.status == "failed" for track in tracks):
        update_album_batch(
            db, batch, status="completed_with_errors", completed_at=datetime.now(timezone.utc)
        )
    else:
        update_album_batch(db, batch, status="completed", completed_at=datetime.now(timezone.utc))


def run_album_worker_tick(db: Session) -> None:
    # One unit of work per call -- advances the single oldest actionable
    # track by one stage. A full 1-hour render or video encode can take
    # real minutes; keeping this to one track per call means a slow stage
    # only delays that call's return, not a batch of unrelated work, and
    # the driving while-loop (apps/worker/app/album_worker.py) naturally
    # re-visits every other track on its next tick.
    tracks = list_actionable_tracks(db, limit=1)

    if not tracks:
        return

    _advance_track(db, tracks[0])
