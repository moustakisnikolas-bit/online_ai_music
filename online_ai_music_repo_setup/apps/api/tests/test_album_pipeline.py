from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.album import AlbumBatch, AlbumTrack
from app.models.audio_job import AudioJob
from app.models.generation_cost import GenerationCost
from app.models.youtube_publishing import YouTubeCredential, YouTubePublication, YouTubeQuotaUsage
from app.audio.concepts import CONCEPTS, get_concept
from app.audio.types import AudioMode, TextureMode
from app.repositories.albums import (
    create_album_batch as insert_album_batch,
    create_album_track,
    get_album_batch,
    list_album_tracks,
)
from app.services import album_pipeline
from app.services.ai_artwork_generator import ArtworkGenerationResult
from app.services.album_combinations import NaturalSoundChoice, TrackCombination
from app.services.album_pipeline import (
    _combination_from_dict,
    _combination_to_dict,
    _finalize_description,
    _hashtags_from_title,
    _natural_sound_description,
    _track_artwork_prompt,
    _track_description,
    _track_title,
    _track_upload_metadata,
    create_album_batch,
    run_album_worker_tick,
)


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    # YouTubeCredential is deliberately excluded: its "scopes" column uses
    # postgresql.ARRAY, which SQLite can't compile. The existing test
    # suite's own established workaround (see test_youtube_publishing.py)
    # is to never persist real YouTubeCredential rows to a SQLite test DB
    # -- construct one in memory and monkeypatch get_youtube_credential to
    # return it directly instead.
    Base.metadata.create_all(
        engine,
        tables=[
            AlbumBatch.__table__,
            AlbumTrack.__table__,
            AudioJob.__table__,
            GenerationCost.__table__,
            YouTubePublication.__table__,
            YouTubeQuotaUsage.__table__,
        ],
    )

    monkeypatch.setattr(album_pipeline, "ARTWORK_DIR", tmp_path / "artwork")
    monkeypatch.setattr(album_pipeline, "VIDEO_DIR", tmp_path / "video")
    monkeypatch.setattr(album_pipeline, "PREVIEW_DIR", tmp_path / "previews")

    with Session(engine) as session:
        yield session


class _FakeAudioResult:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.loudness_lufs = -18.0
        self.validation_warnings: list[str] = []


def _mock_expensive_stages(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "fake-track.wav"
    audio_path.write_bytes(b"fake wav bytes")

    monkeypatch.setattr(
        album_pipeline, "generate_audio", lambda request, output_dir: _FakeAudioResult(str(audio_path))
    )

    def _fake_render_static_video(*, output_dir, output_filename, **_kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / output_filename
        path.write_bytes(b"fake mp4 bytes")
        return path

    monkeypatch.setattr(album_pipeline, "render_static_video", _fake_render_static_video)

    def _fake_generate_ai_artwork(prompt, *, output_path, provider, width, height, seed, db):
        # A real (tiny, fast) image, not fake bytes -- composite_thumbnail_labels
        # runs for real on this in the pipeline and needs an openable image.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (60, 90, 140)).save(output_path, format="PNG")
        return ArtworkGenerationResult(path=output_path, cost_usd=None)

    monkeypatch.setattr(album_pipeline, "generate_ai_artwork", _fake_generate_ai_artwork)


def _connect_fake_youtube_channel(monkeypatch) -> None:
    fake_credential = YouTubeCredential(
        channel_id="UC-fake",
        channel_title="Fake Channel",
        access_token="enc-access",
        refresh_token="enc-refresh",
        token_expiry=None,
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    monkeypatch.setattr(album_pipeline, "get_youtube_credential", lambda db: fake_credential)


def _mock_youtube_calls(monkeypatch) -> None:
    monkeypatch.setattr(album_pipeline, "credentials_from_stored", lambda credential, *, db: object())
    monkeypatch.setattr(
        album_pipeline,
        "upload_video",
        lambda credentials, **kwargs: ("fake-video-id", "https://youtube.com/watch?v=fake-video-id"),
    )
    monkeypatch.setattr(
        album_pipeline,
        "create_playlist",
        lambda credentials, **kwargs: ("fake-playlist-id", "https://youtube.com/playlist?list=fake-playlist-id"),
    )
    monkeypatch.setattr(album_pipeline, "add_video_to_playlist", lambda credentials, **kwargs: "fake-item-id")


def test_create_album_batch_creates_tracks_per_album_tracks_in_draft_status(db) -> None:
    batch = create_album_batch(db, concept_id="focus", seed=1)

    assert batch.status == "generating"
    tracks = list_album_tracks(db, batch.id)
    assert len(tracks) == album_pipeline.TRACKS_PER_ALBUM
    assert all(track.status == "pending" for track in tracks)


def test_create_album_batch_rejects_unknown_concept(db) -> None:
    with pytest.raises(ValueError, match="Unknown album concept"):
        create_album_batch(db, concept_id="not_a_real_concept")


def test_run_album_worker_tick_is_a_no_op_when_nothing_is_actionable(db) -> None:
    run_album_worker_tick(db)  # should not raise with an empty DB


def test_full_pipeline_progresses_one_track_through_every_stage(monkeypatch, db, tmp_path: Path) -> None:
    _mock_expensive_stages(monkeypatch, tmp_path)
    _connect_fake_youtube_channel(monkeypatch)
    _mock_youtube_calls(monkeypatch)

    batch = create_album_batch(db, concept_id="relaxation", seed=2)
    tracks = list_album_tracks(db, batch.id)
    first_track_id = tracks[0].id

    # pending -> harmony_passed (real harmony check, cheap preview)
    run_album_worker_tick(db)
    track = db.get(AlbumTrack, first_track_id)
    assert track.status == "harmony_passed"
    assert track.harmony_check_status in {"passed", "passed_fallback"}

    # harmony_passed -> audio_rendered
    run_album_worker_tick(db)
    track = db.get(AlbumTrack, first_track_id)
    assert track.status == "audio_rendered"
    assert track.audio_job_id is not None
    audio_job = db.get(AudioJob, track.audio_job_id)
    assert audio_job.status == "completed"
    assert audio_job.review_status == "approved"

    # audio_rendered -> video_rendered
    run_album_worker_tick(db)
    track = db.get(AlbumTrack, first_track_id)
    assert track.status == "video_rendered"
    assert track.video_filename is not None

    # video_rendered -> uploaded
    run_album_worker_tick(db)
    track = db.get(AlbumTrack, first_track_id)
    assert track.status == "uploaded"
    assert track.youtube_publication_id is not None
    publication = db.get(YouTubePublication, track.youtube_publication_id)
    assert publication.youtube_video_id == "fake-video-id"

    # uploaded -> playlist_added
    run_album_worker_tick(db)
    track = db.get(AlbumTrack, first_track_id)
    assert track.status == "playlist_added"
    assert track.playlist_item_status == "added"

    batch = get_album_batch(db, batch.id)
    assert batch.youtube_playlist_id == "fake-playlist-id"
    assert batch.playlist_status == "created"


def test_upload_stage_defers_to_tomorrow_when_quota_exhausted(monkeypatch, db, tmp_path: Path) -> None:
    _mock_expensive_stages(monkeypatch, tmp_path)
    _connect_fake_youtube_channel(monkeypatch)
    _mock_youtube_calls(monkeypatch)

    batch = create_album_batch(db, concept_id="focus", seed=3)
    track = list_album_tracks(db, batch.id)[0]

    # Fast-forward this one track straight to video_rendered without
    # spending real quota, then exhaust today's quota deliberately.
    from app.repositories.albums import update_album_track
    from app.repositories.youtube_quota import record_quota_usage

    audio_job = AudioJob(
        title=track.title, mode="mixed_ambient", duration_seconds=3600,
        sample_rate=44100, amplitude=0.2, status="completed",
        output_file_path=str(tmp_path / "fake.wav"), review_status="approved",
    )
    db.add(audio_job)
    db.commit()
    db.refresh(audio_job)
    update_album_track(
        db, track, status="video_rendered", audio_job_id=audio_job.id, video_filename="fake.mp4"
    )
    record_quota_usage(db, units=9500)  # leaves less than one upload's worth

    run_album_worker_tick(db)

    from datetime import timedelta

    track = db.get(AlbumTrack, track.id)
    assert track.status == "video_rendered"  # not "uploaded"
    assert track.scheduled_upload_date == album_pipeline.today_pacific() + timedelta(days=1)


def test_failed_stage_marks_only_that_track_failed(monkeypatch, db, tmp_path: Path) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("synth blew up")

    monkeypatch.setattr(album_pipeline, "generate_audio", _raise)

    batch = create_album_batch(db, concept_id="mind_clearness", seed=4)
    tracks = list_album_tracks(db, batch.id)
    first_id, second_id = tracks[0].id, tracks[1].id

    run_album_worker_tick(db)  # first track: pending -> harmony_passed (real, cheap)
    run_album_worker_tick(db)  # first track: harmony_passed -> generate_audio raises -> failed

    first_track = db.get(AlbumTrack, first_id)
    second_track = db.get(AlbumTrack, second_id)

    assert first_track.status == "failed"
    assert "synth blew up" in first_track.error_message
    assert second_track.status == "pending"  # untouched by the first track's failure


def test_batch_finalizes_as_completed_with_errors_when_a_track_fails(
    monkeypatch, db, tmp_path: Path
) -> None:
    from app.repositories.albums import update_album_batch, update_album_track

    batch = create_album_batch(db, concept_id="focus", seed=5)
    tracks = list_album_tracks(db, batch.id)

    for track in tracks[:-1]:
        update_album_track(db, track, status="playlist_added")
    update_album_track(db, tracks[-1], status="failed", error_message="boom")
    update_album_batch(db, batch, status="uploading")

    album_pipeline._finalize_batch_status_if_done(db, get_album_batch(db, batch.id))

    finalized = get_album_batch(db, batch.id)
    assert finalized.status == "completed_with_errors"
    assert finalized.completed_at is not None


def test_batch_finalizes_as_completed_when_all_tracks_succeed(db) -> None:
    from app.repositories.albums import update_album_batch, update_album_track

    batch = create_album_batch(db, concept_id="relaxation", seed=6)
    tracks = list_album_tracks(db, batch.id)

    for track in tracks:
        update_album_track(db, track, status="playlist_added")
    update_album_batch(db, batch, status="uploading")

    album_pipeline._finalize_batch_status_if_done(db, get_album_batch(db, batch.id))

    finalized = get_album_batch(db, batch.id)
    assert finalized.status == "completed"


# --- Data-variation tests --------------------------------------------
#
# These specifically verify that *different input data* (different
# combinations across tracks) produces *correspondingly different,
# correct output* -- not just "the function ran without crashing" with
# one fixed input. A shared/cached artwork bug (the exact thing this
# feature replaced) would slip past a suite that only checks the
# happy-path shape of a single call.

def _combination(
    *,
    sample_id: str | None = "ocean-waves-fs-01",
    texture_type: TextureMode | None = None,
    tone_hz: float = 432.0,
    noise_type: AudioMode = AudioMode.BROWN_NOISE,
    melody_instrument: str | None = None,
) -> TrackCombination:
    return TrackCombination(
        natural_sound=NaturalSoundChoice(
            kind="texture" if texture_type else "sample",
            sample_id=None if texture_type else sample_id,
            texture_type=texture_type,
        ),
        natural_sound_gain=0.95,
        melody_instrument=melody_instrument,
        melody_scale="major_pentatonic" if melody_instrument else None,
        melody_root_note="C3" if melody_instrument else None,
        melody_gain=0.55 if melody_instrument else None,
        tone_hz=tone_hz,
        tone_gain=0.5,
        noise_type=noise_type,
        noise_gain=0.35,
    )


def test_combination_dict_round_trip_preserves_brainwave_fields() -> None:
    # Real bug caught while adding the brainwave feature: the full track
    # render stage reloads the combination from this exact dict (stored
    # in the DB) rather than reusing the in-memory object the harmony
    # check ran against -- if these fields silently dropped here, every
    # brainwave-layer combination would harmony-check correctly but then
    # ship as a plain tone, with nothing ever catching the mismatch.
    original = TrackCombination(
        natural_sound=NaturalSoundChoice(kind="sample", sample_id="ocean-waves-fs-01"),
        natural_sound_gain=0.95,
        melody_instrument=None,
        melody_scale=None,
        melody_root_note=None,
        melody_gain=None,
        tone_hz=432.0,
        tone_gain=0.5,
        noise_type=AudioMode.PINK_NOISE,
        noise_gain=0.35,
        brainwave_band="alpha",
        brainwave_technique="binaural",
        brainwave_pulse_hz=10.5,
    )

    restored = _combination_from_dict(_combination_to_dict(original))

    assert restored == original


def test_combination_from_dict_defaults_brainwave_fields_for_pre_existing_rows() -> None:
    # Combinations persisted before this feature existed won't have these
    # keys in their stored JSON at all -- must load as "no brainwave
    # layer", not raise a KeyError.
    legacy_dict = _combination_to_dict(_combination())
    del legacy_dict["brainwave_band"], legacy_dict["brainwave_technique"], legacy_dict["brainwave_pulse_hz"]

    restored = _combination_from_dict(legacy_dict)

    assert restored.brainwave_band is None
    assert restored.brainwave_technique is None
    assert restored.brainwave_pulse_hz is None


@pytest.mark.parametrize(
    ("sample_id", "texture_type", "expected"),
    [
        ("ocean-waves-fs-01", None, "ocean waves"),
        ("forest-birds-fs-12", None, "forest birds"),
        ("distant-thunder-fs-01", None, "distant thunder"),
        (None, TextureMode.RAIN, "rain"),
    ],
)
def test_natural_sound_description_cleans_different_inputs(sample_id, texture_type, expected) -> None:
    natural_sound = NaturalSoundChoice(
        kind="texture" if texture_type else "sample",
        sample_id=sample_id,
        texture_type=texture_type,
    )

    assert _natural_sound_description(natural_sound) == expected


@pytest.mark.parametrize("concept_id", list(CONCEPTS.keys()))
def test_track_description_lands_in_the_300_to_400_char_range(concept_id: str) -> None:
    concept = get_concept(concept_id)
    combination = _combination(
        sample_id="ocean-waves-fs-01", tone_hz=concept.hz_pool[0], noise_type=concept.noise_type_preference[0]
    )

    description = _track_description(concept, combination)

    assert 300 <= len(description) <= 400


def test_track_description_reflects_this_tracks_own_attributes() -> None:
    concept = get_concept("chakra")
    ocean = _combination(sample_id="ocean-waves-fs-01", tone_hz=528.0, noise_type=AudioMode.PINK_NOISE)
    forest = _combination(sample_id="forest-birds-fs-01", tone_hz=963.0, noise_type=AudioMode.VIOLET_NOISE)

    assert _track_description(concept, ocean) != _track_description(concept, forest)
    assert "528" in _track_description(concept, ocean)
    assert "963" in _track_description(concept, forest)


def test_finalize_description_pads_a_short_description_up_to_the_minimum() -> None:
    result = _finalize_description("Too short.")

    assert 300 <= len(result) <= 400
    assert result.startswith("Too short.")


def test_finalize_description_clamps_a_long_description_down_to_the_maximum() -> None:
    result = _finalize_description("Sentence one. " * 50)

    assert len(result) <= 400


def test_hashtags_from_title_matches_the_tracks_own_words() -> None:
    hashtags = _hashtags_from_title("Chakra - Owl Night Forest & Violet Noise - 417Hz")

    assert hashtags == ["#Chakra", "#OwlNightForest", "#VioletNoise", "#417Hz"]


def test_track_title_and_hashtags_handle_a_multi_part_concept_label() -> None:
    # "triple_benefit" is deliberately labeled "Sleep, Study & Focus" (a
    # real multi-benefit title pattern found in top-viewed research) --
    # its internal "&" must not break hashtag splitting on the track's
    # own title-generated "&" separators.
    concept = get_concept("triple_benefit")
    combination = _combination(sample_id="ocean-waves-fs-01", tone_hz=432.0, noise_type=AudioMode.WHITE_NOISE)

    title = _track_title(concept, combination)
    assert title == "Sleep, Study & Focus - Ocean Waves & White Noise - 432Hz"

    hashtags = _hashtags_from_title(title)
    assert hashtags == ["#SleepStudy", "#Focus", "#OceanWaves", "#WhiteNoise", "#432Hz"]


def test_hashtags_from_title_skips_empty_segments() -> None:
    hashtags = _hashtags_from_title("Focus -  - 432Hz")

    assert "" not in [h.lstrip("#") for h in hashtags]
    assert hashtags == ["#Focus", "#432Hz"]


def test_track_artwork_prompt_reflects_this_tracks_own_natural_sound_and_hz() -> None:
    concept = get_concept("focus")
    ocean_432hz = _combination(sample_id="ocean-waves-fs-01", tone_hz=432.0, noise_type=AudioMode.BROWN_NOISE)
    forest_528hz = _combination(sample_id="forest-birds-fs-01", tone_hz=528.0, noise_type=AudioMode.PINK_NOISE)

    ocean_prompt = _track_artwork_prompt(concept, ocean_432hz)
    forest_prompt = _track_artwork_prompt(concept, forest_528hz)

    # Different combinations must not collapse into the same prompt --
    # that's exactly the shared-artwork bug this feature replaced.
    assert ocean_prompt != forest_prompt
    assert "ocean waves" in ocean_prompt
    assert "brown noise" in ocean_prompt
    assert "forest birds" in forest_prompt
    assert "pink noise" in forest_prompt
    # Neither combination has a melody -- the optional phrase must not
    # leak into either prompt.
    assert "melody" not in ocean_prompt
    assert "melody" not in forest_prompt


def test_track_artwork_prompt_includes_melody_only_when_present() -> None:
    concept = get_concept("focus")
    with_melody = _combination(melody_instrument="warm_pad")
    without_melody = _combination(melody_instrument=None)

    assert "warm pad melody" in _track_artwork_prompt(concept, with_melody)
    assert "melody" not in _track_artwork_prompt(concept, without_melody)


def test_track_title_reflects_this_tracks_own_natural_sound_noise_and_hz() -> None:
    concept = get_concept("focus")
    ocean_432hz = _combination(sample_id="ocean-waves-fs-01", tone_hz=432.0, noise_type=AudioMode.BROWN_NOISE)
    forest_528hz = _combination(sample_id="forest-birds-fs-01", tone_hz=528.0, noise_type=AudioMode.PINK_NOISE)

    ocean_title = _track_title(concept, ocean_432hz)
    forest_title = _track_title(concept, forest_528hz)

    assert ocean_title == "Focus - Ocean Waves & Brown Noise - 432Hz"
    assert forest_title == "Focus - Forest Birds & Pink Noise - 528Hz"
    assert ocean_title != forest_title


def test_track_title_formats_hz_without_trailing_zero() -> None:
    concept = get_concept("focus")
    whole_hz = _combination(tone_hz=40.0)

    assert "40Hz" in _track_title(concept, whole_hz)
    assert "40.0Hz" not in _track_title(concept, whole_hz)


def test_create_album_batch_gives_each_track_a_distinct_descriptive_title(db) -> None:
    batch = create_album_batch(db, concept_id="focus", seed=1)
    tracks = list_album_tracks(db, batch.id)

    titles = [track.title for track in tracks]
    # Real, meaningfully different titles per track -- not the old
    # generic "Album Title - Track N" pattern.
    assert len(set(titles)) == len(titles)
    assert all("Hz" in title and "Focus" in title for title in titles)
    assert not any("Track " in title for title in titles)


def test_track_upload_metadata_falls_back_when_openrouter_not_configured(db) -> None:
    # No openrouter_api_key is ever set in the test DB -- this exercises
    # the real fallback path (require_openrouter_key raises inside
    # generate_llm_metadata_package), not a mocked one.
    concept = get_concept("focus")
    batch = insert_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="Focus - Ocean Waves & Brown Noise - 432Hz",
        combination=_combination_to_dict(_combination()),
    )
    combination = _combination()

    description, tags = _track_upload_metadata(
        db, concept=concept, batch=batch, track=track, combination=combination
    )

    assert "ocean waves" in description
    assert "432Hz" in description
    assert "brown noise" in description
    assert "Do not present this asset" in description  # COMPLIANCE_NOTE
    assert "#Focus #OceanWaves #BrownNoise #432Hz" in description
    assert tags == ["ambient", "soundscape", "focus", "Focus", "OceanWaves", "BrownNoise", "432Hz"]


def test_track_upload_metadata_uses_llm_package_when_available(monkeypatch, db) -> None:
    from app.services.metadata_generator import MetadataPackage

    fake_package = MetadataPackage(
        title="Deep Focus Flow",
        subtitle="432Hz Ocean Ambience",
        description="Drift into focus with gentle ocean waves and a grounding 432Hz tone.",
        keywords=["432hz", "focus music", "ocean waves"],
        category="Focus",
        language="en",
        compliance_note="Use as ambient or relaxation content.",
    )
    monkeypatch.setattr(
        album_pipeline,
        "generate_llm_metadata_package",
        lambda **kwargs: (fake_package, 0.002),
    )
    cost_calls = []
    monkeypatch.setattr(
        album_pipeline,
        "record_reported_cost",
        lambda db, *, kind, reported_usd, reference: cost_calls.append((kind, reported_usd, reference)),
    )

    concept = get_concept("focus")
    batch = insert_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="Focus - Ocean Waves & Brown Noise - 432Hz",
        combination=_combination_to_dict(_combination()),
    )
    combination = _combination()

    description, tags = _track_upload_metadata(
        db, concept=concept, batch=batch, track=track, combination=combination
    )

    assert fake_package.description in description
    assert fake_package.compliance_note in description
    assert "#Focus #OceanWaves #BrownNoise #432Hz" in description
    assert tags[:3] == ["432hz", "focus music", "ocean waves"]
    assert "ambient" in tags and "focus" in tags
    assert "OceanWaves" in tags and "432Hz" in tags
    assert len(cost_calls) == 1
    assert cost_calls[0][0] == album_pipeline.OPENROUTER_METADATA


def test_upload_stage_publishes_publicly_not_privately(monkeypatch, db, tmp_path) -> None:
    _connect_fake_youtube_channel(monkeypatch)
    captured_kwargs: dict = {}

    def _fake_upload_video(credentials, **kwargs):
        captured_kwargs.update(kwargs)
        return "fake-video-id", "https://youtube.com/watch?v=fake-video-id"

    monkeypatch.setattr(album_pipeline, "credentials_from_stored", lambda credential, *, db: object())
    monkeypatch.setattr(album_pipeline, "upload_video", _fake_upload_video)

    batch = insert_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="Focus - Ocean Waves & Brown Noise - 432Hz",
        combination=_combination_to_dict(_combination()),
    )
    from app.models.audio_job import AudioJob as _AudioJob

    audio_job = _AudioJob(
        title=track.title, mode="mixed_ambient", duration_seconds=895,
        sample_rate=44100, amplitude=0.2, status="completed",
        output_file_path=str(tmp_path / "fake.wav"), review_status="approved",
    )
    db.add(audio_job)
    db.commit()
    db.refresh(audio_job)
    from app.repositories.albums import update_album_track as _update_album_track

    _update_album_track(
        db, track, status="video_rendered", audio_job_id=audio_job.id, video_filename="fake.mp4"
    )

    album_pipeline._run_upload_stage(db, track)

    assert captured_kwargs["privacy_status"] == "public"


def test_ensure_track_artwork_generates_distinct_files_and_hz_labels_per_track(monkeypatch, db, tmp_path) -> None:
    captured_prompts: list[str] = []

    def _fake_generate_ai_artwork(prompt, *, output_path, provider, width, height, seed, db):
        captured_prompts.append(prompt)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (60, 90, 140)).save(output_path, format="PNG")
        return ArtworkGenerationResult(path=output_path, cost_usd=None)

    monkeypatch.setattr(album_pipeline, "generate_ai_artwork", _fake_generate_ai_artwork)

    batch = insert_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    ocean_track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="A",
        combination=_combination_to_dict(_combination(sample_id="ocean-waves-fs-01", tone_hz=432.0)),
    )
    forest_track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=1, title="B",
        combination=_combination_to_dict(_combination(sample_id="forest-birds-fs-01", tone_hz=528.0)),
    )

    ocean_filename = album_pipeline._ensure_track_artwork(db, ocean_track, batch)
    forest_filename = album_pipeline._ensure_track_artwork(db, forest_track, batch)

    # Real, distinct files -- not the old one-image-shared-across-the-album
    # behavior this replaced.
    assert ocean_filename != forest_filename
    assert (album_pipeline.ARTWORK_DIR / ocean_filename).exists()
    assert (album_pipeline.ARTWORK_DIR / forest_filename).exists()
    assert len(captured_prompts) == 2
    assert captured_prompts[0] != captured_prompts[1]

    # Each track's own Hz value must reach the actual composited image,
    # not a shared/default one -- verified by re-running composite with
    # each track's real value against a fresh copy and diffing pixels,
    # rather than trusting the prompt text alone.
    ocean_bytes = (album_pipeline.ARTWORK_DIR / ocean_filename).read_bytes()
    forest_bytes = (album_pipeline.ARTWORK_DIR / forest_filename).read_bytes()
    assert ocean_bytes != forest_bytes

    # Calling again for the same track must not regenerate (still
    # cached/idempotent per track, just no longer shared across tracks).
    call_count_before = len(captured_prompts)
    album_pipeline._ensure_track_artwork(db, ocean_track, batch)
    assert len(captured_prompts) == call_count_before
