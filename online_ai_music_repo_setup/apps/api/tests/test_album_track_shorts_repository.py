from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.album import AlbumBatch, AlbumTrack
from app.models.album_track_short import AlbumTrackShort
from app.repositories.album_track_shorts import (
    create_album_track_short,
    delete_album_track_short,
    get_album_track_short,
    list_actionable_track_shorts,
    list_all_track_shorts,
    list_track_shorts,
    list_tracks_needing_shorts,
    update_album_track_short,
)
from app.repositories.albums import create_album_batch, create_album_track, update_album_track


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[AlbumBatch.__table__, AlbumTrack.__table__, AlbumTrackShort.__table__]
    )

    with Session(engine) as session:
        yield session


def _make_uploaded_track(db, *, status: str = "uploaded") -> AlbumTrack:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="Track A", combination={}
    )
    return update_album_track(db, track, status=status)


def test_create_and_get_round_trip(db) -> None:
    track = _make_uploaded_track(db)
    short = create_album_track_short(
        db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28
    )

    fetched = get_album_track_short(db, short.id)

    assert fetched is not None
    assert fetched.status == "pending"
    assert fetched.clip_index == 0


def test_list_track_shorts_orders_by_clip_index(db) -> None:
    track = _make_uploaded_track(db)
    create_album_track_short(db, album_track_id=track.id, clip_index=2, start_offset_seconds=600, duration_seconds=28)
    create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)
    create_album_track_short(db, album_track_id=track.id, clip_index=1, start_offset_seconds=300, duration_seconds=28)

    shorts = list_track_shorts(db, track.id)

    assert [s.clip_index for s in shorts] == [0, 1, 2]


def test_list_actionable_track_shorts_excludes_terminal_statuses(db) -> None:
    track = _make_uploaded_track(db)
    pending = create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)
    uploaded = create_album_track_short(db, album_track_id=track.id, clip_index=1, start_offset_seconds=300, duration_seconds=28)
    failed = create_album_track_short(db, album_track_id=track.id, clip_index=2, start_offset_seconds=600, duration_seconds=28)
    update_album_track_short(db, uploaded, status="uploaded")
    update_album_track_short(db, failed, status="failed")

    actionable = list_actionable_track_shorts(db)

    assert [s.id for s in actionable] == [pending.id]


def test_list_actionable_track_shorts_excludes_future_scheduled_uploads(db) -> None:
    track = _make_uploaded_track(db)
    deferred = create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)
    next_short = create_album_track_short(db, album_track_id=track.id, clip_index=1, start_offset_seconds=300, duration_seconds=28)
    today = date(2026, 9, 15)
    update_album_track_short(
        db, deferred, status="rendered", scheduled_upload_date=today + timedelta(days=1)
    )

    actionable = list_actionable_track_shorts(db, today=today)

    assert [s.id for s in actionable] == [next_short.id]


def test_list_tracks_needing_shorts_stops_once_shorts_exist(db) -> None:
    track = _make_uploaded_track(db)

    assert [t.id for t in list_tracks_needing_shorts(db)] == [track.id]

    create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)

    assert list_tracks_needing_shorts(db) == []


def test_list_tracks_needing_shorts_excludes_tracks_not_yet_uploaded(db) -> None:
    _make_uploaded_track(db, status="video_rendered")

    assert list_tracks_needing_shorts(db) == []


def test_list_tracks_needing_shorts_includes_playlist_added_tracks(db) -> None:
    track = _make_uploaded_track(db, status="playlist_added")

    assert [t.id for t in list_tracks_needing_shorts(db)] == [track.id]


def test_list_tracks_needing_shorts_respects_backfill_cutoff_date(db) -> None:
    from datetime import datetime, timezone

    track = _make_uploaded_track(db)
    update_album_track(db, track, uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert list_tracks_needing_shorts(db, backfill_cutoff_date=date(2026, 6, 1)) == []
    assert [t.id for t in list_tracks_needing_shorts(db, backfill_cutoff_date=date(2025, 1, 1))] == [track.id]


def test_list_all_track_shorts_orders_newest_first(db) -> None:
    from datetime import datetime, timedelta, timezone

    track = _make_uploaded_track(db)
    first = create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)
    second = create_album_track_short(db, album_track_id=track.id, clip_index=1, start_offset_seconds=300, duration_seconds=28)
    now = datetime.now(timezone.utc)
    update_album_track_short(db, first, created_at=now - timedelta(minutes=1))
    update_album_track_short(db, second, created_at=now)

    shorts = list_all_track_shorts(db)

    assert [s.id for s in shorts] == [second.id, first.id]


def test_update_album_track_short_sets_arbitrary_fields(db) -> None:
    track = _make_uploaded_track(db)
    short = create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)

    updated = update_album_track_short(db, short, status="rendered", video_filename="abc.mp4")

    assert updated.status == "rendered"
    assert updated.video_filename == "abc.mp4"


def test_delete_album_track_short_removes_the_row(db) -> None:
    track = _make_uploaded_track(db)
    short = create_album_track_short(db, album_track_id=track.id, clip_index=0, start_offset_seconds=0, duration_seconds=28)

    delete_album_track_short(db, short)

    assert get_album_track_short(db, short.id) is None
