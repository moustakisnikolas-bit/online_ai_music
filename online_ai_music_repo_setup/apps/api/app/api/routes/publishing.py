import logging
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.config import get_settings
from app.repositories.audio_jobs import get_audio_job
from app.repositories.oauth_state import consume_oauth_state, create_oauth_state
from app.repositories.youtube import (
    create_youtube_publication,
    get_youtube_credential,
    mark_publication_failed,
    mark_publication_uploaded,
    upsert_youtube_credential,
)
from app.repositories.youtube_quota import (
    get_or_create_today_usage,
    record_quota_usage,
    remaining_quota_today,
    today_pacific,
)
from app.schemas.publishing import (
    YouTubeAuthorizationUrlResponse,
    YouTubeConnectionStatusResponse,
    YouTubePublicationResponse,
    YouTubeQuotaStatusResponse,
    YouTubeUploadRequest,
)
from app.services.youtube_publisher import (
    build_authorization_url,
    credentials_from_stored,
    ensure_job_is_publishable,
    exchange_code_for_credentials,
    fetch_channel_identity,
    scopes_cover_playlists,
    set_video_thumbnail,
    upload_video,
)

# A stored credential row existing doesn't mean the token still works --
# it can be dead (expired/revoked refresh token) while still sitting in
# the DB looking "connected." fetch_channel_identity is a real, cheap
# live check, but calling it on every UI poll (every 6s on the Albums
# page) would hammer Google's API for no reason -- cache the result
# briefly instead. Not per-request state, just an in-process TTL cache;
# fine for this single-process app, not meant to survive a restart.
_TOKEN_CHECK_CACHE: dict[str, tuple[float, bool]] = {}
_TOKEN_CHECK_TTL_SECONDS = 300


def _token_is_currently_valid(record, *, db: Session) -> bool:
    cached = _TOKEN_CHECK_CACHE.get(record.channel_id)
    now = time.monotonic()

    if cached is not None and (now - cached[0]) < _TOKEN_CHECK_TTL_SECONDS:
        return cached[1]

    try:
        credentials = credentials_from_stored(record, db=db)
        # credentials_from_stored's own `if not credentials.valid` guard
        # never fires in practice -- it constructs Credentials without an
        # expiry, and google-auth treats "no expiry" as "never expired,"
        # so a stale cached access token gets reused as-is. That's fine
        # for real uploads (the transport layer retries-with-refresh on
        # a 401), but it means "did this call succeed" doesn't actually
        # prove the *refresh token* still works -- an unexpired cached
        # access token would pass right through it. Force the refresh
        # explicitly so this check tests the thing that actually dies
        # (invalid_grant on the refresh token), not the access token's
        # leftover shelf life.
        credentials.refresh(GoogleAuthRequest())
        fetch_channel_identity(credentials)
        valid = True
    except Exception:  # noqa: BLE001 -- any failure here means "not usable right now"
        valid = False

    _TOKEN_CHECK_CACHE[record.channel_id] = (now, valid)
    return valid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publishing/youtube", tags=["publishing"])

VIDEO_DIR = Path("data/generated/video")
ARTWORK_DIR = Path("data/generated/artwork")


def _resolve_within(directory: Path, filename: str) -> Path | None:
    candidate = (directory / filename).resolve()

    if candidate.parent != directory.resolve() or not candidate.exists():
        return None

    return candidate


@router.get("/authorize", response_model=YouTubeAuthorizationUrlResponse)
def authorize_youtube(db: Session = Depends(get_db)) -> YouTubeAuthorizationUrlResponse:
    state = secrets.token_urlsafe(32)

    try:
        authorization_url = build_authorization_url(state, db=db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    create_oauth_state(db, state=state, purpose="youtube")

    return YouTubeAuthorizationUrlResponse(
        authorization_url=authorization_url,
        state=state,
    )


def _callback_redirect(*, success: bool, reason: str | None = None) -> RedirectResponse:
    if success:
        return RedirectResponse(url="/app?youtube_connect=success")

    query = f"youtube_connect=error&reason={quote(reason or 'unknown_error')}"
    return RedirectResponse(url=f"/app?{query}")


@router.get("/callback", include_in_schema=False)
def youtube_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # Google (and every other OAuth2 provider) redirects the browser back
    # here with a GET request and the result in the query string -- it
    # never POSTs a JSON body. This handler receives exactly what the
    # browser is actually sent, then hands control back to the app's own
    # page with the outcome in the URL so the UI can show it.
    if error:
        return _callback_redirect(success=False, reason=error)

    if not code or not state:
        return _callback_redirect(success=False, reason="missing_parameters")

    if not consume_oauth_state(db, state=state, purpose="youtube"):
        return _callback_redirect(success=False, reason="invalid_or_expired_state")

    try:
        credentials = exchange_code_for_credentials(code, db=db)
        channel_id, channel_title = fetch_channel_identity(credentials)
    except ValueError as exc:
        return _callback_redirect(success=False, reason=str(exc))

    upsert_youtube_credential(
        db,
        channel_id=channel_id,
        channel_title=channel_title,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_expiry=credentials.expiry,
        scopes=list(credentials.scopes or []),
    )

    return _callback_redirect(success=True)


@router.get("/status", response_model=YouTubeConnectionStatusResponse)
def youtube_connection_status(
    db: Session = Depends(get_db),
) -> YouTubeConnectionStatusResponse:
    record = get_youtube_credential(db)

    if record is None:
        return YouTubeConnectionStatusResponse(connected=False)

    return YouTubeConnectionStatusResponse(
        connected=_token_is_currently_valid(record, db=db),
        channel_id=record.channel_id,
        channel_title=record.channel_title,
        connected_at=record.connected_at,
        has_playlist_scope=scopes_cover_playlists(record.scopes),
    )


@router.get("/quota", response_model=YouTubeQuotaStatusResponse)
def youtube_quota_status(db: Session = Depends(get_db)) -> YouTubeQuotaStatusResponse:
    settings = get_settings()
    budget = settings.youtube_daily_quota_budget
    remaining = remaining_quota_today(db, budget=budget)
    usage = get_or_create_today_usage(db)

    pacific = ZoneInfo("America/Los_Angeles")
    tomorrow_pacific_midnight = datetime.combine(
        today_pacific() + timedelta(days=1), datetime.min.time(), tzinfo=pacific
    )

    return YouTubeQuotaStatusResponse(
        units_used=usage.units_used,
        daily_budget=budget,
        remaining=remaining,
        uploads_remaining_today=max(
            0,
            (remaining - settings.youtube_quota_safety_margin_units)
            // settings.youtube_upload_quota_cost_units,
        ),
        resets_at=tomorrow_pacific_midnight,
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

    video_path = _resolve_within(VIDEO_DIR, payload.video_filename)

    if video_path is None:
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
        credentials = credentials_from_stored(credential, db=db)
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

    # This manual, single-video flow shares the same Google Cloud project
    # quota as the album pipeline's automated uploads -- without recording
    # usage here too, the pipeline's quota pacer would over-schedule
    # relative to what's actually been spent.
    record_quota_usage(db, units=get_settings().youtube_upload_quota_cost_units)

    thumbnail_set = False

    if payload.artwork_filename is not None:
        artwork_path = _resolve_within(ARTWORK_DIR, payload.artwork_filename)

        if artwork_path is not None:
            try:
                set_video_thumbnail(
                    credentials, video_id=video_id, thumbnail_path=artwork_path
                )
                thumbnail_set = True
            except Exception:
                # The video itself already uploaded successfully -- a
                # thumbnail failure shouldn't fail the whole publish, but
                # thumbnail_set=False on the response makes it visible
                # rather than silently claiming success.
                logger.warning(
                    "Failed to set YouTube thumbnail for video %s", video_id, exc_info=True
                )

    return mark_publication_uploaded(
        db,
        publication,
        youtube_video_id=video_id,
        youtube_url=video_url,
        thumbnail_set=thumbnail_set,
    )
