import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.audio.concepts import list_concepts
from app.repositories.albums import (
    get_album_batch,
    list_album_batches,
    list_album_tracks,
    update_album_batch,
)
from app.schemas.album import (
    AlbumBatchCreateRequest,
    AlbumBatchDetailResponse,
    AlbumBatchResponse,
    AlbumConceptResponse,
    AlbumTrackResponse,
)
from app.services.album_pipeline import create_album_batch

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/concepts", response_model=list[AlbumConceptResponse])
def list_album_concepts() -> list[dict]:
    return list_concepts()


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
