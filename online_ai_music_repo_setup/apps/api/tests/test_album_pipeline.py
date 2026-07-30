from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.album import AlbumBatch, AlbumTrack
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubeCredential, YouTubePublication, YouTubeQuotaUsage
from app.repositories.albums import get_album_batch, list_album_tracks
from app.services import album_pipeline
from app.services.album_pipeline import create_album_batch, run_album_worker_tick


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


def test_create_album_batch_creates_ten_tracks_in_draft_status(db) -> None:
    batch = create_album_batch(db, concept_id="focus", seed=1)

    assert batch.status == "generating"
    tracks = list_album_tracks(db, batch.id)
    assert len(tracks) == 10
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
