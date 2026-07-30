import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.album import AlbumBatch, AlbumTrack
from app.repositories.albums import (
    create_album_batch,
    create_album_track,
    get_album_batch,
    list_actionable_tracks,
    list_album_batches,
    list_album_tracks,
    update_album_batch,
    update_album_track,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AlbumBatch.__table__, AlbumTrack.__table__])

    with Session(engine) as session:
        yield session


def test_create_album_batch_defaults_to_draft(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")

    assert batch.status == "draft"
    assert batch.concept_id == "focus"


def test_create_album_track_defaults_to_pending(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db,
        album_batch_id=batch.id,
        sequence_index=0,
        title="Focus Vol. 1 - Track 1",
        combination={"tone_hz": 432.0},
    )

    assert track.status == "pending"
    assert track.harmony_check_status == "pending"
    assert track.combination == {"tone_hz": 432.0}


def test_get_album_batch_returns_none_when_missing(db) -> None:
    import uuid

    assert get_album_batch(db, uuid.uuid4()) is None


def test_list_album_batches_orders_newest_first(db) -> None:
    from datetime import datetime, timedelta, timezone

    # SQLite's CURRENT_TIMESTAMP only has 1-second resolution, so two rows
    # created back-to-back in a fast test can collide on created_at even
    # though Postgres (the real backend) has microsecond resolution and
    # wouldn't -- set explicit, clearly-ordered timestamps so this test
    # verifies the ORDER BY logic itself, not real-time succession.
    first = create_album_batch(db, concept_id="focus", title="First")
    second = create_album_batch(db, concept_id="relaxation", title="Second")
    now = datetime.now(timezone.utc)
    update_album_batch(db, first, created_at=now - timedelta(minutes=1))
    update_album_batch(db, second, created_at=now)

    batches = list_album_batches(db)

    assert [b.id for b in batches] == [second.id, first.id]


def test_list_album_tracks_orders_by_sequence(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    create_album_track(db, album_batch_id=batch.id, sequence_index=2, title="C", combination={})
    create_album_track(db, album_batch_id=batch.id, sequence_index=0, title="A", combination={})
    create_album_track(db, album_batch_id=batch.id, sequence_index=1, title="B", combination={})

    tracks = list_album_tracks(db, batch.id)

    assert [t.title for t in tracks] == ["A", "B", "C"]


def test_list_actionable_tracks_excludes_terminal_statuses(db) -> None:
    # "uploaded" is deliberately NOT terminal -- it still needs to reach
    # "playlist_added" -- so only playlist_added/failed tracks should be
    # excluded here.
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    pending_track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="Pending", combination={}
    )
    uploaded_track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=1, title="Uploaded", combination={}
    )
    playlist_added_track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=2, title="Playlist Added", combination={}
    )
    update_album_track(db, uploaded_track, status="uploaded")
    update_album_track(db, playlist_added_track, status="playlist_added")

    actionable = list_actionable_tracks(db)

    assert {t.id for t in actionable} == {pending_track.id, uploaded_track.id}


def test_list_actionable_tracks_excludes_cancelled_batches(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    create_album_track(db, album_batch_id=batch.id, sequence_index=0, title="A", combination={})
    update_album_batch(db, batch, status="cancelled")

    assert list_actionable_tracks(db) == []


def test_update_album_track_sets_arbitrary_fields(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")
    track = create_album_track(
        db, album_batch_id=batch.id, sequence_index=0, title="A", combination={}
    )

    updated = update_album_track(
        db, track, status="harmony_passed", harmony_check_status="passed"
    )

    assert updated.status == "harmony_passed"
    assert updated.harmony_check_status == "passed"


def test_update_album_batch_sets_arbitrary_fields(db) -> None:
    batch = create_album_batch(db, concept_id="focus", title="Focus Vol. 1")

    updated = update_album_batch(db, batch, status="uploading")

    assert updated.status == "uploading"
