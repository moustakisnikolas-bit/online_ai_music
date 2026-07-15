from pathlib import Path

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.core.config import get_settings
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubeCredential

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_API_SERVICE_NAME = "youtube"
_API_VERSION = "v3"


def _client_config() -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.youtube_client_id,
            "client_secret": settings.youtube_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.youtube_redirect_uri],
        }
    }


def _ensure_oauth_configured() -> None:
    settings = get_settings()

    if not settings.youtube_client_id or not settings.youtube_client_secret:
        raise ValueError(
            "YouTube OAuth is not configured: set YOUTUBE_CLIENT_ID and "
            "YOUTUBE_CLIENT_SECRET."
        )


def build_authorization_url(state: str) -> str:
    _ensure_oauth_configured()
    settings = get_settings()

    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )

    return authorization_url


def exchange_code_for_credentials(code: str) -> Credentials:
    _ensure_oauth_configured()
    settings = get_settings()

    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
    )
    flow.fetch_token(code=code)

    return flow.credentials


def fetch_channel_identity(credentials: Credentials) -> tuple[str, str | None]:
    service = build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)
    response = service.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])

    if not items:
        raise ValueError("No YouTube channel is associated with this account.")

    channel = items[0]
    return channel["id"], channel.get("snippet", {}).get("title")


def credentials_from_stored(record: YouTubeCredential) -> Credentials:
    settings = get_settings()
    credentials = Credentials(
        token=record.access_token,
        refresh_token=record.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
        scopes=record.scopes or SCOPES,
    )

    if not credentials.valid:
        credentials.refresh(GoogleAuthRequest())

    return credentials


def ensure_job_is_publishable(job: AudioJob | None) -> AudioJob:
    if job is None:
        raise ValueError("Audio job not found.")

    if job.status != "completed":
        raise ValueError("Only completed audio jobs can be published.")

    if job.review_status != "approved":
        raise ValueError(
            "This audio job has not been approved for publishing. "
            f"Current review status: {job.review_status}."
        )

    return job


def upload_video(
    credentials: Credentials,
    *,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
) -> tuple[str, str]:
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    service = build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )
    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None

    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_id, video_url
