import uuid
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.album import AlbumTrack
from app.models.album_track_short import AlbumTrackShort

# Mirrors app/repositories/albums.py's TERMINAL_TRACK_STATUSES convention.
# "uploaded" IS terminal for a short (unlike AlbumTrack, where "uploaded" is
# deliberately non-terminal pending a playlist step) -- shorts have no
# playlist stage in v1, see app/services/shorts_pipeline.py.
TERMINAL_SHORT_STATUSES = {"uploaded", "failed"}
# A track only becomes shorts-eligible once its own long-form video is a
# real, confirmed publish -- "uploaded" or further along ("playlist_added").
# Never "video_rendered" or earlier, so a track that fails its own upload
# never spawns shorts for content that isn't actually live yet.
SHORTS_ELIGIBLE_TRACK_STATUSES = {"uploaded", "playlist_added"}


def create_album_track_short(
    db: Session,
    *,
    album_track_id: uuid.UUID,
    clip_index: int,
    start_offset_seconds: int,
    duration_seconds: int,
) -> AlbumTrackShort:
    short = AlbumTrackShort(
        album_track_id=album_track_id,
        clip_index=clip_index,
        start_offset_seconds=start_offset_seconds,
        duration_seconds=duration_seconds,
        status="pending",
    )
    db.add(short)
    db.commit()
    db.refresh(short)
    return short


def get_album_track_short(db: Session, short_id: uuid.UUID) -> AlbumTrackShort | None:
    return db.get(AlbumTrackShort, short_id)


def list_track_shorts(db: Session, album_track_id: uuid.UUID) -> list[AlbumTrackShort]:
    statement = (
        select(AlbumTrackShort)
        .where(AlbumTrackShort.album_track_id == album_track_id)
        .order_by(AlbumTrackShort.clip_index)
    )
    return list(db.scalars(statement))


def list_all_track_shorts(db: Session, *, limit: int = 50) -> list[AlbumTrackShort]:
    statement = (
        select(AlbumTrackShort)
        .order_by(AlbumTrackShort.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_actionable_track_shorts(
    db: Session, *, limit: int = 20, today: date | None = None
) -> list[AlbumTrackShort]:
    # Excludes a short whose upload got deferred to tomorrow (quota
    # exhausted) -- mirrors list_actionable_tracks in albums.py exactly,
    # same starvation reason: without this, a quota-blocked "rendered"
    # short would keep winning this FIFO ordering every tick and block
    # every other short (including ones only needing a render, not
    # quota) until quota resets.
    if today is None:
        today = datetime.now(timezone.utc).date()

    statement = (
        select(AlbumTrackShort)
        .where(
            AlbumTrackShort.status.not_in(TERMINAL_SHORT_STATUSES),
            or_(
                AlbumTrackShort.scheduled_upload_date.is_(None),
                AlbumTrackShort.scheduled_upload_date <= today,
            ),
        )
        .order_by(AlbumTrackShort.created_at)
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_tracks_needing_shorts(
    db: Session, *, limit: int = 1, backfill_cutoff_date: date | None = None
) -> list[AlbumTrack]:
    # Outer join against AlbumTrackShort, filtered to zero existing
    # children -- a track stops appearing here the instant its shorts get
    # spawned (idempotency), regardless of how far those shorts later get.
    statement = (
        select(AlbumTrack)
        .outerjoin(AlbumTrackShort, AlbumTrackShort.album_track_id == AlbumTrack.id)
        .where(
            AlbumTrack.status.in_(SHORTS_ELIGIBLE_TRACK_STATUSES),
            AlbumTrackShort.id.is_(None),
        )
        .order_by(AlbumTrack.created_at)
        .limit(limit)
    )

    if backfill_cutoff_date is not None:
        statement = statement.where(AlbumTrack.uploaded_at >= backfill_cutoff_date)

    return list(db.scalars(statement))


def update_album_track_short(db: Session, short: AlbumTrackShort, **fields) -> AlbumTrackShort:
    for key, value in fields.items():
        setattr(short, key, value)

    db.commit()
    db.refresh(short)
    return short


def delete_album_track_short(db: Session, short: AlbumTrackShort) -> None:
    db.delete(short)
    db.commit()
