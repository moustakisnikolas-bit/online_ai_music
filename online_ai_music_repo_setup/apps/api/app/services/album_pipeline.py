import logging
import re
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
    delete_album_batch as _delete_album_batch_row,
    delete_album_track as _delete_album_track_row,
    get_album_batch,
    list_actionable_tracks,
    list_album_tracks,
    update_album_batch,
    update_album_track,
)
from app.repositories.audio_jobs import get_audio_job
from app.repositories.generation_costs import (
    FLUX_REPLICATE,
    OPENROUTER_METADATA,
    record_estimated_cost,
    record_reported_cost,
)
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
from app.services.ai_artwork_generator import generate_ai_artwork
from app.services.artwork_generator import PRESETS, composite_thumbnail_labels
from app.services.audio_generator import generate_audio
from app.services.llm_metadata_generator import generate_llm_metadata_package
from app.services.metadata_generator import compliance_note_for
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
#
# 14:55, not 15:00 or 60:00 -- YouTube blocks uploads over 15 minutes for
# accounts that haven't gone through its longer-video verification, and
# a real batch actually hit this (5 real 1-hour uploads got rejected).
# 895s keeps a safety margin under the exact 900s cutoff rather than
# riding the line.
TRACK_DURATION_SECONDS = 14 * 60 + 55
# Single source of truth for how many tracks a new album batch gets --
# every other reference (docs, UI progress display) reads the real
# track_summary/track count from the API rather than hardcoding this
# number, so it never drifts out of sync with this value again.
TRACKS_PER_ALBUM = 5
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
        "brainwave_band": combination.brainwave_band,
        "brainwave_technique": combination.brainwave_technique,
        "brainwave_pulse_hz": combination.brainwave_pulse_hz,
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
        # .get(...) not [...] -- combinations persisted before this field
        # existed don't have these keys; treat that as "no brainwave
        # layer" rather than a KeyError.
        brainwave_band=data.get("brainwave_band"),
        brainwave_technique=data.get("brainwave_technique"),
        brainwave_pulse_hz=data.get("brainwave_pulse_hz"),
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

    combinations = generate_candidate_combinations(concept_id, count=TRACKS_PER_ALBUM, seed=seed)
    # A too-small real+fallback pool could return fewer than
    # TRACKS_PER_ALBUM unique combinations -- pad with the safe fallback
    # rather than short an album, since the fallback is guaranteed valid.
    while len(combinations) < TRACKS_PER_ALBUM:
        combinations.append(safe_fallback_combination(concept_id))

    for index, combination in enumerate(combinations):
        create_album_track(
            db,
            album_batch_id=batch.id,
            sequence_index=index,
            title=_track_title(concept, combination),
            combination=_combination_to_dict(combination),
        )

    return update_album_batch(db, batch, status="generating")


def album_has_published_tracks(db: Session, batch: AlbumBatch) -> bool:
    """True if any track in this batch has actually reached YouTube --
    the signal callers use to refuse a plain delete (see delete_album)."""
    return any(
        track.youtube_publication_id is not None or track.uploaded_at is not None
        for track in list_album_tracks(db, batch.id)
    )


def _delete_generated_file_quietly(path: Path) -> None:
    # Best-effort cleanup -- a file already missing (partial render, prior
    # manual cleanup) shouldn't block deleting the album's DB records.
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete generated file %s during album delete", path, exc_info=True)


def delete_album(db: Session, batch: AlbumBatch) -> int:
    """Permanently deletes an album batch, its tracks, and their locally
    generated audio/artwork/video files. Deliberately does not touch
    YouTube -- deleting these DB rows can't un-publish a real video, so
    callers must refuse (or get explicit confirmation) when
    album_has_published_tracks() is true; see the DELETE /albums/{id}
    route for that check.
    """
    tracks = list_album_tracks(db, batch.id)

    for track in tracks:
        if track.video_filename:
            _delete_generated_file_quietly(VIDEO_DIR / track.video_filename)
        if track.artwork_filename:
            _delete_generated_file_quietly(ARTWORK_DIR / track.artwork_filename)
        if track.audio_job_id:
            audio_job = get_audio_job(db, track.audio_job_id)
            if audio_job and audio_job.output_file_path:
                _delete_generated_file_quietly(Path(audio_job.output_file_path))

    for track in tracks:
        _delete_album_track_row(db, track)

    _delete_album_batch_row(db, batch)
    return len(tracks)


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


def _natural_sound_description(natural_sound: NaturalSoundChoice) -> str:
    raw = natural_sound.sample_id or (
        natural_sound.texture_type.value if natural_sound.texture_type else "ambient"
    )
    # Sample-library filenames carry recording-source suffixes (e.g.
    # "ocean-waves-fs-01") that read fine as an id but not as a prompt
    # phrase -- strip those and turn separators into spaces so the AI
    # prompt gets "ocean waves", not "ocean-waves-fs-01".
    cleaned = re.sub(r"-fs-\d+$", "", raw)
    return cleaned.replace("-", " ").replace("_", " ")


def _track_title(concept, combination: TrackCombination) -> str:
    # Descriptive, SEO-relevant title built from this track's own real
    # combination data (concept + natural sound + noise type + Hz) --
    # same source data as the artwork prompt and thumbnail Hz label, so
    # title/thumbnail/audio never disagree about what the track actually
    # is. Replaces the old generic "Album Title - Track N".
    natural_sound_desc = _natural_sound_description(combination.natural_sound).title()
    noise_desc = combination.noise_type.value.replace("_", " ").title()
    return f"{concept.label} - {natural_sound_desc} & {noise_desc} - {combination.tone_hz:g}Hz"


def _track_artwork_prompt(concept, combination: TrackCombination) -> str:
    purpose = get_purpose(concept.purpose_id)
    natural_sound_desc = _natural_sound_description(combination.natural_sound)
    noise_desc = combination.noise_type.value.replace("_", " ")
    melody_phrase = (
        f", a faint {combination.melody_instrument.replace('_', ' ')} melody drifting through"
        if combination.melody_instrument
        else ""
    )
    return (
        f"Photorealistic, high-detail photo evoking {natural_sound_desc}, capturing the "
        f"feeling of {concept.label.lower()}: {purpose.description.lower()} A subtle "
        f"{noise_desc} atmosphere{melody_phrase}. Calm, soothing, cinematic lighting, "
        f"vibrant natural colors, no text or typography in the image."
    )


def _ensure_track_artwork(db: Session, track: AlbumTrack, batch: AlbumBatch) -> str:
    # One real, unique AI photo per track (not shared across the album)
    # so each of the 10 thumbnails actually reflects that track's own
    # natural sound/melody/noise combination instead of one generic
    # concept image repeated ten times. Replicate only, deliberately --
    # not a provider-selectable path like the manual artwork route, per
    # an explicit choice to keep album artwork on one provider. The
    # concept name and Hz value are composited on afterward as real
    # text (see composite_thumbnail_labels), not asked of the AI model,
    # which renders text unreliably.
    concept = get_concept(batch.concept_id)
    combination = _combination_from_dict(track.combination)
    filename = f"track-{track.id}.png"
    target_path = ARTWORK_DIR / filename

    if target_path.exists():
        return filename

    preset = PRESETS["youtube-thumbnail"]
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


def _run_video_render_stage(db: Session, track: AlbumTrack) -> None:
    audio_job = get_audio_job(db, track.audio_job_id)
    audio_filename = Path(audio_job.output_file_path).name
    batch = get_album_batch(db, track.album_batch_id)
    artwork_filename = _ensure_track_artwork(db, track, batch)
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


_DESCRIPTION_MIN_CHARS = 300
_DESCRIPTION_MAX_CHARS = 400

# One curiosity-driven opener per concept, grounded in what that concept
# actually is (not generic ad copy) -- the "intrigue viewers to click"
# hook the rest of the description builds on.
_DESCRIPTION_HOOKS: dict[str, str] = {
    "focus": "Ever wondered what real deep work actually sounds like?",
    "relaxation": "Feel the tension start to let go before the first minute is up.",
    "mind_clearness": "Clear the mental fog in minutes, not hours.",
    "sleep": "The last thing you'll remember before drifting off.",
    "healing": "One old frequency, one very modern kind of stillness.",
    "study": "The soundtrack focused students swear by.",
    "chakra": "Seven energy centers, one frequency at a time.",
    "deep_focus": "Not just focus -- the kind that makes hours disappear.",
    "deep_relaxation": "Past relaxed. All the way to still.",
    "deep_mind_clearness": "The fog doesn't just lift here -- it stays gone.",
    "deep_sleep": "For the nights when 'tired' isn't cutting it anymore.",
    "deep_healing": "The frequency real listeners come back to on their hardest days.",
    "deep_study": "Built for the session that has to actually work.",
    "deep_chakra": "All seven centers, taken further than the usual pass.",
    "triple_benefit": "One soundscape, three real jobs: fall asleep, cram, or just focus.",
    "baby_white_noise": "The sound real parents reach for at 3am.",
    "baby_womb": "The sound they heard for nine months, still working.",
    "baby_shush": "A steady, patient hush -- built to outlast the crying.",
    "baby_lullaby": "A gentle melody built for the last five minutes before sleep.",
    "baby_rain": "Soft rain, nothing else -- built to fade into the background.",
}

# Appended one at a time only until the description clears
# _DESCRIPTION_MIN_CHARS -- keeps short natural-sound/Hz combinations
# from shipping an under-length description without padding every
# track with all of them regardless of length.
_DESCRIPTION_FILLERS = (
    " No lyrics, no ads mid-track -- just one continuous, real soundscape from AION.",
    " Built for headphones, but honest enough to hold up on speakers too.",
    " Give it two minutes and notice how hard it is to tell where the tone ends and the room begins.",
    " Every layer here is real audio, not a loop you'll notice repeating.",
)


def _pad_description(description: str) -> str:
    for filler in _DESCRIPTION_FILLERS:
        if len(description) >= _DESCRIPTION_MIN_CHARS:
            break
        description += filler
    return description


def _clamp_description(description: str) -> str:
    if len(description) <= _DESCRIPTION_MAX_CHARS:
        return description

    truncated = description[:_DESCRIPTION_MAX_CHARS]
    last_period = truncated.rfind(". ")
    if last_period > _DESCRIPTION_MIN_CHARS - 50:
        return truncated[: last_period + 1]
    return truncated.rsplit(" ", 1)[0] + "."


def _finalize_description(description: str) -> str:
    # Applied to both the LLM-generated description (whose exact length
    # the prompt can request but not guarantee) and the deterministic
    # fallback below, so 300-400 chars holds regardless of which path
    # produced it.
    return _clamp_description(_pad_description(description))


def _track_description(concept, combination: TrackCombination) -> str:
    """A deterministic, no-LLM-required description sized to the
    300-400 char range -- built from this track's own real attributes
    (natural sound, Hz, noise color), not generic boilerplate, so it
    still reads as written for this specific track when OpenRouter
    isn't configured.
    """
    natural = _natural_sound_description(combination.natural_sound)
    noise_label = combination.noise_type.value.replace("_", " ")
    hook = _DESCRIPTION_HOOKS.get(concept.id, "Press play and notice what changes.")

    description = (
        f"{hook} This {concept.label} soundscape layers real {natural} with a "
        f"steady {combination.tone_hz:g}Hz tone and soft {noise_label} underneath."
    )
    return _finalize_description(description)


def _hashtags_from_title(title: str) -> list[str]:
    """Turns a track's own descriptive title into real hashtags, e.g.
    "Chakra - Owl Night Forest & Violet Noise - 417Hz" becomes
    ["#Chakra", "#OwlNightForest", "#VioletNoise", "#417Hz"] -- reuses
    the title's own words rather than a separate hashtag vocabulary, so
    the hashtags always match what the video is actually titled.
    """
    hashtags = []
    for segment in re.split(r"[-&]", title):
        cleaned = re.sub(r"[^A-Za-z0-9]+", "", segment)
        if cleaned:
            hashtags.append(f"#{cleaned}")
    return hashtags


def _track_upload_metadata(
    db: Session, *, concept, batch: AlbumBatch, track: AlbumTrack, combination: TrackCombination
) -> tuple[str, list[str]]:
    """Real, per-track SEO description/tags via the LLM metadata
    generator when OpenRouter is configured; a deterministic per-track
    description otherwise. An LLM failure (no key configured, bad
    response, network error) falls back rather than failing the whole
    upload over what's ultimately a nice-to-have, not a required step.
    Both paths get the same 300-400 char clamp and the same
    title-derived hashtags appended, in the description text and the
    tags list.
    """
    hashtags = _hashtags_from_title(track.title)
    hashtag_words = [tag.lstrip("#") for tag in hashtags]
    hashtag_line = " ".join(hashtags)

    try:
        package, cost_usd = generate_llm_metadata_package(
            source_title=track.title,
            mode="mixed_ambient",
            duration_seconds=TRACK_DURATION_SECONDS,
            db=db,
            context=concept.id,
            frequency_hz=combination.tone_hz,
            texture_mode=combination.noise_type.value,
        )
    except Exception:  # noqa: BLE001 -- optional enhancement, must never block a real upload
        logger.warning(
            "LLM metadata generation failed for track %s, using fallback description/tags",
            track.id,
            exc_info=True,
        )
        fallback_description = _track_description(concept, combination)
        description = f"{fallback_description}\n\n{compliance_note_for(concept.id)}\n\n{hashtag_line}"
        tags = ["ambient", "soundscape", concept.id, *hashtag_words]
        return description, tags

    record_reported_cost(db, kind=OPENROUTER_METADATA, reported_usd=cost_usd, reference=str(track.id))

    description = f"{_finalize_description(package.description)}\n\n{package.compliance_note}\n\n{hashtag_line}"
    # Dedup while preserving order (LLM keywords first, base tags as a
    # findability floor) -- a plain set() would make tag order random.
    tags = list(dict.fromkeys([*package.keywords, "ambient", concept.id, *hashtag_words]))
    return description, tags


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
    combination = _combination_from_dict(track.combination)
    video_path = (VIDEO_DIR / track.video_filename).resolve()

    publication = create_youtube_publication(
        db,
        audio_job_id=track.audio_job_id,
        video_filename=track.video_filename,
        title=track.title,
    )

    description, tags = _track_upload_metadata(
        db, concept=concept, batch=batch, track=track, combination=combination
    )

    try:
        credentials = credentials_from_stored(credential, db=db)
        video_id, video_url = upload_video(
            credentials,
            video_path=video_path,
            title=track.title,
            description=description,
            tags=tags,
            category_id="10",
            # Public, not private -- the entire point of this pipeline is
            # real views on real published content; a private upload is
            # invisible to search/browse and defeats that.
            privacy_status="public",
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
    tracks = list_actionable_tracks(db, limit=1, today=today_pacific())

    if not tracks:
        return

    _advance_track(db, tracks[0])
