import uuid
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.album import AlbumBatch, AlbumTrack

# Terminal states, used to find batches/tracks the pacer still needs to
# act on. Kept here (not on the model) since it's a query concern, not a
# data concern.
TERMINAL_BATCH_STATUSES = {"completed", "completed_with_errors", "cancelled"}
# "uploaded" is deliberately NOT terminal -- it still needs to advance to
# "playlist_added" (see album_pipeline.py's state machine).
TERMINAL_TRACK_STATUSES = {"playlist_added", "failed"}


def create_album_batch(db: Session, *, concept_id: str, title: str) -> AlbumBatch:
    batch = AlbumBatch(concept_id=concept_id, title=title, status="draft")
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def create_album_track(
    db: Session,
    *,
    album_batch_id: uuid.UUID,
    sequence_index: int,
    title: str,
    combination: dict,
) -> AlbumTrack:
    track = AlbumTrack(
        album_batch_id=album_batch_id,
        sequence_index=sequence_index,
        title=title,
        combination=combination,
        status="pending",
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def get_album_batch(db: Session, batch_id: uuid.UUID) -> AlbumBatch | None:
    return db.get(AlbumBatch, batch_id)


def list_album_batches(db: Session, *, limit: int = 50) -> list[AlbumBatch]:
    statement = select(AlbumBatch).order_by(AlbumBatch.created_at.desc()).limit(limit)
    return list(db.scalars(statement))


def list_album_tracks(db: Session, album_batch_id: uuid.UUID) -> list[AlbumTrack]:
    statement = (
        select(AlbumTrack)
        .where(AlbumTrack.album_batch_id == album_batch_id)
        .order_by(AlbumTrack.sequence_index)
    )
    return list(db.scalars(statement))


def list_actionable_tracks(db: Session, *, limit: int = 20, today: date | None = None) -> list[AlbumTrack]:
    # Oldest non-cancelled batch first, then sequence order within a
    # batch -- keeps a batch's tracks progressing together rather than
    # one batch racing ahead while another starves.
    #
    # scheduled_upload_date in the future means the upload stage already
    # found quota exhausted and deferred -- without excluding those here,
    # such a track (still non-terminal) keeps winning the sequence_index
    # ordering on every single tick, forever re-running the same losing
    # quota check and starving every other track in the batch (including
    # ones that don't need quota at all, like harmony-check or video
    # render) until quota resets. Once its date arrives, it's picked up
    # again naturally -- the upload stage still does its own live check,
    # so this is purely a scheduling fix, not a new gating rule.
    if today is None:
        today = datetime.now(timezone.utc).date()

    statement = (
        select(AlbumTrack)
        .join(AlbumBatch, AlbumTrack.album_batch_id == AlbumBatch.id)
        .where(
            AlbumTrack.status.not_in(TERMINAL_TRACK_STATUSES),
            AlbumBatch.status.not_in(TERMINAL_BATCH_STATUSES),
            or_(AlbumTrack.scheduled_upload_date.is_(None), AlbumTrack.scheduled_upload_date <= today),
        )
        .order_by(AlbumBatch.created_at, AlbumTrack.sequence_index)
        .limit(limit)
    )
    return list(db.scalars(statement))


def update_album_track(db: Session, track: AlbumTrack, **fields) -> AlbumTrack:
    for key, value in fields.items():
        setattr(track, key, value)

    db.commit()
    db.refresh(track)
    return track


def update_album_batch(db: Session, batch: AlbumBatch, **fields) -> AlbumBatch:
    for key, value in fields.items():
        setattr(batch, key, value)

    db.commit()
    db.refresh(batch)
    return batch
