from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.album import AlbumBatch, AlbumTrack
from app.models.album_track_short import AlbumTrackShort
from app.models.audio_job import AudioJob
from app.models.generation_cost import GenerationCost
from app.models.youtube_publishing import YouTubeCredential, YouTubePublication, YouTubeQuotaUsage
from app.repositories.album_track_shorts import list_track_shorts
from app.repositories.albums import create_album_batch, create_album_track, update_album_track
from app.services import shorts_pipeline
from app.services.ai_artwork_generator import ArtworkGenerationResult
from app.services.album_combinations import safe_fallback_combination
from app.services.album_pipeline import TRACK_DURATION_SECONDS, _combination_to_dict
from app.services.shorts_pipeline import (
    _compute_start_offsets,
    _ensure_track_shorts,
    run_shorts_worker_tick,
)


class _FakeShortsSettings:
    shorts_enabled = True
    shorts_per_track = 3
    shorts_duration_seconds = 28
    shorts_width = 1080
    shorts_height = 1920
    shorts_privacy_status = "public"
    shorts_backfill_cutoff_date = None
    youtube_daily_quota_budget = 10000
    youtube_upload_quota_cost_units = 1600
    youtube_quota_safety_margin_units = 800
    flux_replicate_cost_usd = 0.003
    audio_output_path: Path


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            AlbumBatch.__table__,
            AlbumTrack.__table__,
            AlbumTrackShort.__table__,
            AudioJob.__table__,
            GenerationCost.__table__,
            YouTubePublication.__table__,
            YouTubeQuotaUsage.__table__,
        ],
    )

    monkeypatch.setattr(shorts_pipeline, "ARTWORK_DIR", tmp_path / "artwork")
    monkeypatch.setattr(shorts_pipeline, "VIDEO_DIR", tmp_path / "video")

    fake_settings = _FakeShortsSettings()
    fake_settings.audio_output_path = tmp_path / "audio"
    monkeypatch.setattr(shorts_pipeline, "get_settings", lambda: fake_settings)

    with Session(engine) as session:
        yield session


def _make_track(db, tmp_path, *, status: str, concept_id: str = "focus") -> AlbumTrack:
    batch = create_album_batch(db, concept_id=concept_id, title="Focus Vol. 1")
    combination = _combination_to_dict(safe_fallback_combination(concept_id))
    track = create_album_track(
        db,
        album_batch_id=batch.id,
        sequence_index=0,
        title="Focus - Ocean Waves & Pink Noise - 432Hz",
        combination=combination,
    )

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{track.id}.wav"
    audio_path.write_bytes(b"fake wav bytes")

    audio_job = AudioJob(
        title=track.title,
        mode="mixed_ambient",
        channels="stereo",
        duration_seconds=TRACK_DURATION_SECONDS,
        status="completed",
        output_file_path=str(audio_path),
        review_status="approved",
    )
    db.add(audio_job)
    db.commit()
    db.refresh(audio_job)

    return update_album_track(db, track, status=status, audio_job_id=audio_job.id)


def _mock_expensive_shorts_stages(monkeypatch, artwork_calls: list | None = None) -> None:
    def _fake_generate_ai_artwork(prompt, *, output_path, provider, width, height, seed, db):
        if artwork_calls is not None:
            artwork_calls.append(1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (50, 80, 120)).save(output_path, format="PNG")
        return ArtworkGenerationResult(path=output_path, cost_usd=None)

    monkeypatch.setattr(shorts_pipeline, "generate_ai_artwork", _fake_generate_ai_artwork)

    def _fake_render_static_video(*, output_dir, output_filename, **_kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / output_filename
        path.write_bytes(b"fake mp4 bytes")
        return path

    monkeypatch.setattr(shorts_pipeline, "render_static_video", _fake_render_static_video)


def _connect_fake_youtube_channel(monkeypatch) -> None:
    fake_credential = YouTubeCredential(
        channel_id="UC-fake",
        channel_title="Fake Channel",
        access_token="enc-access",
        refresh_token="enc-refresh",
        token_expiry=None,
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    monkeypatch.setattr(shorts_pipeline, "get_youtube_credential", lambda db: fake_credential)


def _mock_youtube_calls(monkeypatch) -> None:
    monkeypatch.setattr(shorts_pipeline, "credentials_from_stored", lambda credential, *, db: object())
    monkeypatch.setattr(
        shorts_pipeline,
        "upload_video",
        lambda credentials, **kwargs: ("fake-short-id", "https://youtube.com/shorts/fake-short-id"),
    )


# --- offsets ---------------------------------------------------------


def test_compute_start_offsets_spreads_clips_evenly() -> None:
    offsets = _compute_start_offsets(5, 28)

    assert offsets[0] == 0
    assert offsets[-1] == TRACK_DURATION_SECONDS - 28
    assert offsets == sorted(offsets)
    assert len(offsets) == 5


def test_compute_start_offsets_handles_a_single_clip() -> None:
    assert _compute_start_offsets(1, 28) == [0]


def test_compute_start_offsets_handles_zero_clips() -> None:
    assert _compute_start_offsets(0, 28) == []


# --- spawn eligibility -------------------------------------------------


def test_shorts_are_not_spawned_before_the_track_is_uploaded(monkeypatch, db, tmp_path: Path) -> None:
    _make_track(db, tmp_path, status="video_rendered")

    run_shorts_worker_tick(db)

    assert db.query(AlbumTrackShort).count() == 0


def test_shorts_are_not_spawned_for_a_failed_track(monkeypatch, db, tmp_path: Path) -> None:
    # Regression guard for the "falls out naturally, no special-case"
    # design -- a track (of ANY concept, including a deliberately paused
    # one like baby_shush) that never reaches "uploaded" must never spawn
    # shorts, with no concept-id check anywhere in this code path.
    _make_track(db, tmp_path, status="failed", concept_id="baby_shush")

    run_shorts_worker_tick(db)

    assert db.query(AlbumTrackShort).count() == 0


def test_shorts_spawn_once_the_track_reaches_uploaded(monkeypatch, db, tmp_path: Path) -> None:
    track = _make_track(db, tmp_path, status="uploaded")

    run_shorts_worker_tick(db)

    shorts = list_track_shorts(db, track.id)
    assert len(shorts) == _FakeShortsSettings.shorts_per_track
    assert [s.clip_index for s in shorts] == [0, 1, 2]
    assert all(s.status == "pending" for s in shorts)


def test_shorts_spawn_is_a_no_op_when_shorts_enabled_is_false(monkeypatch, db, tmp_path: Path) -> None:
    _make_track(db, tmp_path, status="uploaded")
    monkeypatch.setattr(shorts_pipeline.get_settings(), "shorts_enabled", False)

    run_shorts_worker_tick(db)

    assert db.query(AlbumTrackShort).count() == 0


def test_ensure_track_shorts_is_idempotent(db, tmp_path: Path) -> None:
    track = _make_track(db, tmp_path, status="uploaded")

    _ensure_track_shorts(db, track)
    run_shorts_worker_tick(db)  # would spawn a second batch if not for the zero-shorts guard

    assert db.query(AlbumTrackShort).count() == _FakeShortsSettings.shorts_per_track


# --- render + shared artwork ---------------------------------------------


def test_all_shorts_of_one_track_share_a_single_vertical_artwork(
    monkeypatch, db, tmp_path: Path
) -> None:
    # Each tick advances whichever one short is oldest-and-actionable by
    # exactly one stage (mirrors album_pipeline's one-row-per-tick
    # design), so a short fully completes pending -> rendered -> uploaded
    # before the next one is ever touched -- youtube must be mocked here
    # too, or the second stage of the first short raises.
    artwork_calls: list = []
    _mock_expensive_shorts_stages(monkeypatch, artwork_calls)
    _connect_fake_youtube_channel(monkeypatch)
    _mock_youtube_calls(monkeypatch)
    track = _make_track(db, tmp_path, status="uploaded")

    run_shorts_worker_tick(db)  # spawn
    for _ in range(_FakeShortsSettings.shorts_per_track * 2):
        run_shorts_worker_tick(db)  # render then upload, per short

    shorts = list_track_shorts(db, track.id)
    assert all(s.status == "uploaded" for s in shorts)
    assert len({s.artwork_filename for s in shorts}) == 1
    assert len(artwork_calls) == 1


# --- full lifecycle -------------------------------------------------------


def test_full_short_lifecycle_pending_to_rendered_to_uploaded(
    monkeypatch, db, tmp_path: Path
) -> None:
    _mock_expensive_shorts_stages(monkeypatch)
    _connect_fake_youtube_channel(monkeypatch)
    _mock_youtube_calls(monkeypatch)
    track = _make_track(db, tmp_path, status="uploaded")

    run_shorts_worker_tick(db)  # spawn shorts_per_track shorts
    shorts = list_track_shorts(db, track.id)
    first_short_id = shorts[0].id

    run_shorts_worker_tick(db)  # pending -> rendered (oldest short)
    short = db.get(AlbumTrackShort, first_short_id)
    assert short.status == "rendered"
    assert short.video_filename == f"{short.id}.mp4"
    assert (shorts_pipeline.VIDEO_DIR / short.video_filename).exists()

    run_shorts_worker_tick(db)  # rendered -> uploaded (same short: oldest actionable)
    short = db.get(AlbumTrackShort, first_short_id)
    assert short.status == "uploaded"
    assert short.youtube_publication_id is not None

    publication = db.get(YouTubePublication, short.youtube_publication_id)
    assert publication.video_kind == "short"
    assert publication.youtube_video_id == "fake-short-id"


def test_quota_exhaustion_defers_a_shorts_upload(monkeypatch, db, tmp_path: Path) -> None:
    _mock_expensive_shorts_stages(monkeypatch)
    _connect_fake_youtube_channel(monkeypatch)
    _mock_youtube_calls(monkeypatch)
    track = _make_track(db, tmp_path, status="uploaded")

    run_shorts_worker_tick(db)  # spawn
    run_shorts_worker_tick(db)  # pending -> rendered

    # Exhaust today's quota exactly like test_upload_stage_defers_to_tomorrow_when_quota_exhausted.
    from app.repositories.youtube_quota import record_quota_usage

    record_quota_usage(db, units=_FakeShortsSettings.youtube_daily_quota_budget)

    shorts = list_track_shorts(db, track.id)
    rendered_short_id = shorts[0].id

    run_shorts_worker_tick(db)

    short = db.get(AlbumTrackShort, rendered_short_id)
    assert short.status == "rendered"  # not uploaded
    assert short.scheduled_upload_date is not None
