from pathlib import Path

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubeCredential
from app.services.secrets import resolve_secret
from app.services.token_encryption import decrypt_token

# youtube.upload alone can insert/update/delete videos but can't read
# channel info -- fetch_channel_identity()'s channels().list(mine=True)
# call needs youtube.readonly too, or Google rejects it with "Insufficient
# Permission" even though the token exchange itself succeeded.
SCOPES = [
    # The single broad scope supersedes both youtube.upload and
    # youtube.readonly, and additionally covers playlists.insert /
    # playlistItems.insert (needed for the album pipeline's "album" =
    # playlist support), which neither of the narrower scopes cover.
    "https://www.googleapis.com/auth/youtube",
]
# Scopes that satisfy playlist read/write, for checking an *already*
# connected credential's stored grant (see scopes_cover_playlists) --
# separate from SCOPES above, which is only what new authorizations
# request.
_PLAYLIST_CAPABLE_SCOPES = {
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
}
_API_SERVICE_NAME = "youtube"
_API_VERSION = "v3"


def _client_config(client_id: str, client_secret: str) -> dict:
    settings = get_settings()
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.youtube_redirect_uri],
        }
    }


def _ensure_oauth_configured(db: Session) -> tuple[str, str]:
    client_id = resolve_secret(db, "youtube_client_id")
    client_secret = resolve_secret(db, "youtube_client_secret")

    if not client_id or not client_secret:
        raise ValueError(
            "YouTube OAuth is not configured: set a YouTube client ID and "
            "client secret in Settings (or YOUTUBE_CLIENT_ID / "
            "YOUTUBE_CLIENT_SECRET)."
        )

    return client_id, client_secret


def build_authorization_url(state: str, *, db: Session) -> str:
    client_id, client_secret = _ensure_oauth_configured(db)
    settings = get_settings()

    flow = Flow.from_client_config(
        _client_config(client_id, client_secret),
        scopes=SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
        # PKCE's code_verifier only helps if the same Flow object survives
        # from the authorize request to the callback request -- ours don't
        # (each is a separate, stateless HTTP request). This is a
        # confidential client (it has a client secret), so PKCE isn't
        # required; auto-generating a verifier we can never supply back
        # would just make Google reject the exchange with "Missing code
        # verifier" instead.
        autogenerate_code_verifier=False,
    )

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )

    return authorization_url


def exchange_code_for_credentials(code: str, *, db: Session) -> Credentials:
    client_id, client_secret = _ensure_oauth_configured(db)
    settings = get_settings()

    flow = Flow.from_client_config(
        _client_config(client_id, client_secret),
        scopes=SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
        autogenerate_code_verifier=False,
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


def credentials_from_stored(record: YouTubeCredential, *, db: Session) -> Credentials:
    credentials = Credentials(
        token=decrypt_token(record.access_token),
        refresh_token=decrypt_token(record.refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=resolve_secret(db, "youtube_client_id"),
        client_secret=resolve_secret(db, "youtube_client_secret"),
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


def set_video_thumbnail(
    credentials: Credentials,
    *,
    video_id: str,
    thumbnail_path: Path,
) -> None:
    if not thumbnail_path.exists():
        raise FileNotFoundError(thumbnail_path)

    service = build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)
    media = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
    service.thumbnails().set(videoId=video_id, media_body=media).execute()


def scopes_cover_playlists(scopes: list[str] | None) -> bool:
    # Lets the /publishing/youtube/status route tell the UI whether to
    # prompt "re-authorize for playlist support" specifically, rather than
    # the UI guessing from "connected" alone -- a connection made before
    # this feature existed only has youtube.upload + youtube.readonly on
    # its stored grant, which doesn't cover playlist writes.
    if not scopes:
        return False

    return bool(_PLAYLIST_CAPABLE_SCOPES.intersection(scopes))


def create_playlist(
    credentials: Credentials,
    *,
    title: str,
    description: str,
    privacy_status: str = "private",
) -> tuple[str, str]:
    service = build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }
    response = service.playlists().insert(part="snippet,status", body=body).execute()

    playlist_id = response["id"]
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    return playlist_id, playlist_url


def add_video_to_playlist(
    credentials: Credentials,
    *,
    playlist_id: str,
    video_id: str,
) -> str:
    service = build(_API_SERVICE_NAME, _API_VERSION, credentials=credentials)

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    response = service.playlistItems().insert(part="snippet", body=body).execute()

    return response["id"]
