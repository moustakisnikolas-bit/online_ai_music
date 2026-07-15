import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.repositories.audio_jobs import get_audio_job
from app.repositories.youtube import (
    create_youtube_publication,
    get_youtube_credential,
    mark_publication_failed,
    mark_publication_uploaded,
    upsert_youtube_credential,
)
from app.schemas.publishing import (
    YouTubeAuthorizationUrlResponse,
    YouTubeCallbackRequest,
    YouTubeConnectionStatusResponse,
    YouTubePublicationResponse,
    YouTubeUploadRequest,
)
from app.services.youtube_publisher import (
    build_authorization_url,
    credentials_from_stored,
    ensure_job_is_publishable,
    exchange_code_for_credentials,
    fetch_channel_identity,
    upload_video,
)

router = APIRouter(prefix="/publishing/youtube", tags=["publishing"])

VIDEO_DIR = Path("data/generated/video")


@router.get("/authorize", response_model=YouTubeAuthorizationUrlResponse)
def authorize_youtube() -> YouTubeAuthorizationUrlResponse:
    state = secrets.token_urlsafe(32)

    try:
        authorization_url = build_authorization_url(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return YouTubeAuthorizationUrlResponse(
        authorization_url=authorization_url,
        state=state,
    )


@router.post("/callback", response_model=YouTubeConnectionStatusResponse)
def youtube_oauth_callback(
    payload: YouTubeCallbackRequest,
    db: Session = Depends(get_db),
) -> YouTubeConnectionStatusResponse:
    try:
        credentials = exchange_code_for_credentials(payload.code)
        channel_id, channel_title = fetch_channel_identity(credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    record = upsert_youtube_credential(
        db,
        channel_id=channel_id,
        channel_title=channel_title,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_expiry=credentials.expiry,
        scopes=list(credentials.scopes or []),
    )

    return YouTubeConnectionStatusResponse(
        connected=True,
        channel_id=record.channel_id,
        channel_title=record.channel_title,
        connected_at=record.connected_at,
    )


@router.get("/status", response_model=YouTubeConnectionStatusResponse)
def youtube_connection_status(
    db: Session = Depends(get_db),
) -> YouTubeConnectionStatusResponse:
    record = get_youtube_credential(db)

    if record is None:
        return YouTubeConnectionStatusResponse(connected=False)

    return YouTubeConnectionStatusResponse(
        connected=True,
        channel_id=record.channel_id,
        channel_title=record.channel_title,
        connected_at=record.connected_at,
    )


@router.post("/uploads", response_model=YouTubePublicationResponse)
def upload_to_youtube(
    payload: YouTubeUploadRequest,
    db: Session = Depends(get_db),
) -> YouTubePublicationResponse:
    job = get_audio_job(db, payload.audio_job_id)

    try:
        job = ensure_job_is_publishable(job)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    credential = get_youtube_credential(db)

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No YouTube channel is connected. Complete the OAuth flow first.",
        )

    video_path = (VIDEO_DIR / payload.video_filename).resolve()

    if video_path.parent != VIDEO_DIR.resolve() or not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found.",
        )

    publication = create_youtube_publication(
        db,
        audio_job_id=job.id,
        video_filename=payload.video_filename,
        title=payload.title,
    )

    try:
        credentials = credentials_from_stored(credential)
        video_id, video_url = upload_video(
            credentials,
            video_path=video_path,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            category_id=payload.category_id,
            privacy_status=payload.privacy_status,
        )
    except Exception as exc:
        publication = mark_publication_failed(db, publication, error_message=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"YouTube upload failed: {exc}",
        ) from exc

    return mark_publication_uploaded(
        db,
        publication,
        youtube_video_id=video_id,
        youtube_url=video_url,
    )
