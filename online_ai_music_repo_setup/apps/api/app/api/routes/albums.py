import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.audio.concepts import CONCEPTS, list_concepts
from app.models.album import AlbumTrack
from app.models.youtube_publishing import YouTubePublication
from app.repositories.album_track_shorts import (
    delete_album_track_short,
    get_album_track_short,
    list_all_track_shorts,
)
from app.repositories.albums import (
    get_album_batch,
    list_album_batches,
    list_album_tracks,
    update_album_batch,
)
from app.repositories.concept_research import list_concept_research
from app.schemas.album import (
    AlbumBatchCreateRequest,
    AlbumBatchDetailResponse,
    AlbumBatchResponse,
    AlbumConceptResponse,
    AlbumTrackResponse,
    AlbumTrackShortResponse,
    AlbumTrackShortsListResponse,
    ConceptResearchResponse,
)
from app.services.album_pipeline import (
    VIDEO_DIR,
    _delete_generated_file_quietly,
    album_has_published_tracks,
    create_album_batch,
    delete_album,
)
from app.services.concept_research import research_concept

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/concepts", response_model=list[AlbumConceptResponse])
def list_album_concepts() -> list[dict]:
    return list_concepts()


# Both routes below are deliberately registered before /{album_id} (a
# UUID path param) -- same defensive ordering as /concepts itself, even
# though FastAPI/Starlette's actual route matching is by path shape
# (segment count + literal-vs-param), not registration order alone, so a
# 2-segment "/concepts/research" can't structurally collide with the
# 1-segment "/{album_id}" anyway. Kept together for readability.
@router.get("/concepts/research", response_model=list[ConceptResearchResponse])
def list_album_concept_research(db: Session = Depends(get_db)) -> list[ConceptResearchResponse]:
    """Cached real-world research (no live API call, no quota cost) --
    see POST .../research to trigger a fresh one."""
    return [ConceptResearchResponse.model_validate(r) for r in list_concept_research(db)]


@router.post("/concepts/{concept_id}/research", response_model=ConceptResearchResponse)
def trigger_concept_research(
    concept_id: str,
    db: Session = Depends(get_db),
) -> ConceptResearchResponse:
    """Runs a real YouTube search for this concept's niche and persists
    the result -- a real API call with real quota cost (~103 units),
    not free, so this is only triggered on demand, never automatically.
    """
    if concept_id not in CONCEPTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown concept: {concept_id!r}",
        )

    try:
        record = research_concept(db, concept_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ConceptResearchResponse.model_validate(record)


def _track_summary(db: Session, batch_id: uuid.UUID) -> dict[str, int]:
    summary: dict[str, int] = {}

    for track in list_album_tracks(db, batch_id):
        summary[track.status] = summary.get(track.status, 0) + 1

    return summary


@router.post("", response_model=AlbumBatchResponse)
def create_album(
    payload: AlbumBatchCreateRequest,
    db: Session = Depends(get_db),
) -> AlbumBatchResponse:
    try:
        batch = create_album_batch(
            db, concept_id=payload.concept_id, title=payload.title, seed=payload.seed
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    response = AlbumBatchResponse.model_validate(batch)
    response.track_summary = _track_summary(db, batch.id)
    return response


@router.get("", response_model=list[AlbumBatchResponse])
def list_albums(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[AlbumBatchResponse]:
    responses = []

    for batch in list_album_batches(db, limit=limit):
        response = AlbumBatchResponse.model_validate(batch)
        response.track_summary = _track_summary(db, batch.id)
        responses.append(response)

    return responses


# Registered before /{album_id} for the same structural reason as
# /concepts above -- "/shorts" would otherwise be swallowed by the
# 1-segment /{album_id} route and fail UUID parsing instead of ever
# reaching this handler.
@router.get("/shorts", response_model=AlbumTrackShortsListResponse)
def list_track_shorts_endpoint(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> AlbumTrackShortsListResponse:
    shorts = list_all_track_shorts(db, limit=limit)
    summary: dict[str, int] = {}
    items: list[AlbumTrackShortResponse] = []

    for short in shorts:
        summary[short.status] = summary.get(short.status, 0) + 1

        track = db.get(AlbumTrack, short.album_track_id)
        youtube_url = None
        if short.youtube_publication_id is not None:
            publication = db.get(YouTubePublication, short.youtube_publication_id)
            youtube_url = publication.youtube_url if publication else None

        response = AlbumTrackShortResponse.model_validate(short)
        response.track_title = track.title if track else ""
        response.concept_id = "" if track is None else get_album_batch(db, track.album_batch_id).concept_id
        response.youtube_url = youtube_url
        items.append(response)

    return AlbumTrackShortsListResponse(summary=summary, shorts=items)


@router.delete("/shorts/{short_id}")
def delete_track_short_endpoint(
    short_id: uuid.UUID,
    force: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    short = get_album_track_short(db, short_id)

    if short is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short not found.",
        )

    publication = None
    if short.youtube_publication_id is not None:
        publication = db.get(YouTubePublication, short.youtube_publication_id)

    if not force and publication is not None and publication.youtube_video_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This short has already been published to YouTube. Deleting it here "
                "will not remove the video from YouTube. Pass ?force=true to delete anyway."
            ),
        )

    if short.video_filename:
        _delete_generated_file_quietly(VIDEO_DIR / short.video_filename)
    # The artwork file is deliberately NOT deleted -- it's the parent
    # track's one SHARED vertical image, reused by every other short of
    # that same track (see shorts_pipeline._ensure_track_vertical_artwork).
    # Deleting one short must never break the others still relying on it.

    delete_album_track_short(db, short)

    return {"deleted": True, "short_id": str(short_id)}


@router.get("/{album_id}", response_model=AlbumBatchDetailResponse)
def get_album(
    album_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AlbumBatchDetailResponse:
    batch = get_album_batch(db, album_id)

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found.",
        )

    tracks = list_album_tracks(db, album_id)
    response = AlbumBatchDetailResponse.model_validate(batch)
    response.tracks = [AlbumTrackResponse.model_validate(track) for track in tracks]
    response.track_summary = _track_summary(db, album_id)
    return response


@router.post("/{album_id}/cancel", response_model=AlbumBatchResponse)
def cancel_album(
    album_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AlbumBatchResponse:
    batch = get_album_batch(db, album_id)

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found.",
        )

    # Tracks already uploaded/added to a playlist are left alone -- this
    # only stops the pacer from doing any further work on this batch's
    # remaining tracks (list_actionable_tracks excludes cancelled batches).
    batch = update_album_batch(db, batch, status="cancelled")

    response = AlbumBatchResponse.model_validate(batch)
    response.track_summary = _track_summary(db, album_id)
    return response


@router.delete("/{album_id}")
def delete_album_endpoint(
    album_id: uuid.UUID,
    force: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    batch = get_album_batch(db, album_id)

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Album not found.",
        )

    # Deleting these DB rows can't un-publish a real YouTube video, so a
    # batch with any already-published track is refused by default --
    # force=true is an explicit "yes, I know, just clean up my records".
    if not force and album_has_published_tracks(db, batch):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This album has tracks already published to YouTube. Deleting it here "
                "will not remove those videos from YouTube. Pass ?force=true to delete anyway."
            ),
        )

    tracks_deleted = delete_album(db, batch)

    return {"deleted": True, "album_id": str(album_id), "tracks_deleted": tracks_deleted}
