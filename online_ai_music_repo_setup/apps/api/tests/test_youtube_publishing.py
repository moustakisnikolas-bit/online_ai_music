import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubeCredential
from app.schemas.publishing import YouTubeUploadRequest
from app.services import secrets as secrets_service
from app.services import token_encryption, youtube_publisher


class _FakeSettings:
    youtube_client_id = "test-client-id"
    youtube_client_secret = "test-client-secret"
    youtube_redirect_uri = "http://localhost:8000/api/v1/publishing/youtube/callback"


class _EmptySettings:
    youtube_client_id = ""
    youtube_client_secret = ""
    youtube_redirect_uri = "http://localhost:8000/api/v1/publishing/youtube/callback"


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AppSecret.__table__])

    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", tmp_path / ".local_secret_key")

    class _EmptyEncryptionSettings:
        token_encryption_key = ""

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptyEncryptionSettings())

    with Session(engine) as session:
        yield session


class _FakeInsertRequest:
    def __init__(self, response: dict) -> None:
        self._response = response

    def next_chunk(self):
        return None, self._response


class _FakeDeleteRequest:
    def __init__(self, calls: list[str], video_id: str) -> None:
        self._calls = calls
        self._video_id = video_id

    def execute(self):
        self._calls.append(self._video_id)
        return None


class _FakeVideosResource:
    def __init__(self, response: dict, delete_calls: list[str] | None = None) -> None:
        self._response = response
        self._delete_calls = delete_calls if delete_calls is not None else []

    def insert(self, **_kwargs):
        return _FakeInsertRequest(self._response)

    def delete(self, *, id):  # noqa: A002 -- matches the real googleapiclient method's kwarg name
        return _FakeDeleteRequest(self._delete_calls, id)


class _FakeYouTubeService:
    def __init__(self, response: dict | None = None, delete_calls: list[str] | None = None) -> None:
        self._response = response
        self._delete_calls = delete_calls if delete_calls is not None else []

    def videos(self):
        return _FakeVideosResource(self._response, self._delete_calls)


class _FakeChannelsResource:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def list(self, **_kwargs):
        return self

    def execute(self):
        return {"items": self._items}


class _FakeChannelsService:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def channels(self):
        return _FakeChannelsResource(self._items)


class _FakeSearchResource:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def list(self, **_kwargs):
        return self

    def execute(self):
        return {"items": self._items}


class _FakeVideoStatsResource:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def list(self, **_kwargs):
        return self

    def execute(self):
        return {"items": self._items}


class _FakeSearchService:
    def __init__(self, search_items: list[dict], stats_items: list[dict]) -> None:
        self._search_items = search_items
        self._stats_items = stats_items

    def search(self):
        return _FakeSearchResource(self._search_items)

    def videos(self):
        return _FakeVideoStatsResource(self._stats_items)


class _FakeSetThumbnailRequest:
    def __init__(self, calls: list[dict], video_id: str, media_body) -> None:
        self._calls = calls
        self._video_id = video_id
        self._media_body = media_body

    def execute(self):
        self._calls.append({"videoId": self._video_id, "media_body": self._media_body})
        return {}


class _FakeThumbnailsResource:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def set(self, *, videoId, media_body):
        return _FakeSetThumbnailRequest(self._calls, videoId, media_body)


class _FakeThumbnailsService:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def thumbnails(self):
        return _FakeThumbnailsResource(self._calls)


class _FakePlaylistsInsertRequest:
    def __init__(self, response: dict) -> None:
        self._response = response

    def execute(self):
        return self._response


class _FakePlaylistsResource:
    def __init__(self, response: dict) -> None:
        self._response = response

    def insert(self, **_kwargs):
        return _FakePlaylistsInsertRequest(self._response)


class _FakePlaylistItemsInsertRequest:
    def __init__(self, calls: list[dict], kwargs: dict, response: dict) -> None:
        self._calls = calls
        self._kwargs = kwargs
        self._response = response

    def execute(self):
        self._calls.append(self._kwargs)
        return self._response


class _FakePlaylistItemsResource:
    def __init__(self, calls: list[dict], response: dict) -> None:
        self._calls = calls
        self._response = response

    def insert(self, **kwargs):
        return _FakePlaylistItemsInsertRequest(self._calls, kwargs, self._response)


class _FakePlaylistService:
    def __init__(self, playlists_response: dict | None = None, playlist_items_response: dict | None = None) -> None:
        self._playlists_response = playlists_response or {}
        self._playlist_items_response = playlist_items_response or {}
        self.playlist_item_calls: list[dict] = []

    def playlists(self):
        return _FakePlaylistsResource(self._playlists_response)

    def playlistItems(self):
        return _FakePlaylistItemsResource(self.playlist_item_calls, self._playlist_items_response)


def test_scopes_cover_playlists_true_for_broad_scope() -> None:
    assert youtube_publisher.scopes_cover_playlists(["https://www.googleapis.com/auth/youtube"]) is True


def test_scopes_cover_playlists_false_for_narrow_legacy_scopes() -> None:
    legacy_scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    assert youtube_publisher.scopes_cover_playlists(legacy_scopes) is False


def test_scopes_cover_playlists_false_for_none_or_empty() -> None:
    assert youtube_publisher.scopes_cover_playlists(None) is False
    assert youtube_publisher.scopes_cover_playlists([]) is False


def test_importing_youtube_publisher_relaxes_oauthlib_token_scope_check() -> None:
    import os

    assert os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE") == "1"


def test_incremental_authorization_scope_mismatch_no_longer_raises(monkeypatch) -> None:
    # Real reproduction of the actual bug: Google's incremental
    # authorization (include_granted_scopes="true") returns a token whose
    # granted scope is the union of every scope ever approved for this
    # app, not just the single scope this Flow requested -- which is
    # exactly what a re-authorization for playlist support does. Confirm
    # oauthlib's own scope-mismatch parser, called directly (not through
    # our wrapper), no longer raises once youtube_publisher has been
    # imported -- this is what turned every real re-auth attempt into a
    # 500 before the fix.
    from oauthlib.oauth2.rfc6749.parameters import parse_token_response

    requested_scope = "https://www.googleapis.com/auth/youtube"
    granted_scope = (
        "https://www.googleapis.com/auth/youtube.upload "
        "https://www.googleapis.com/auth/youtube.readonly "
        "https://www.googleapis.com/auth/youtube"
    )
    body = (
        '{"access_token": "fake-token", "token_type": "Bearer", '
        f'"expires_in": 3600, "scope": "{granted_scope}"}}'
    )

    # No env var manipulation here -- relies on the real side effect of
    # importing youtube_publisher (already imported at module load
    # above), same as what actually happens in the running app.
    token = parse_token_response(body, scope=requested_scope)

    assert token["access_token"] == "fake-token"


def test_create_playlist_returns_id_and_url(monkeypatch) -> None:
    fake_service = _FakePlaylistService(playlists_response={"id": "PL123"})
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    playlist_id, playlist_url = youtube_publisher.create_playlist(
        object(), title="Focus Vol. 1", description="10 focus tracks"
    )

    assert playlist_id == "PL123"
    assert playlist_url == "https://www.youtube.com/playlist?list=PL123"


def test_add_video_to_playlist_calls_playlist_items_insert(monkeypatch) -> None:
    fake_service = _FakePlaylistService(playlist_items_response={"id": "PLI456"})
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    item_id = youtube_publisher.add_video_to_playlist(
        object(), playlist_id="PL123", video_id="V789"
    )

    assert item_id == "PLI456"
    assert len(fake_service.playlist_item_calls) == 1
    body = fake_service.playlist_item_calls[0]["body"]
    assert body["snippet"]["playlistId"] == "PL123"
    assert body["snippet"]["resourceId"]["videoId"] == "V789"


def test_ensure_job_is_publishable_requires_job() -> None:
    with pytest.raises(ValueError, match="not found"):
        youtube_publisher.ensure_job_is_publishable(None)


def test_ensure_job_is_publishable_requires_completed_status() -> None:
    job = AudioJob(title="t", mode="sine", duration_seconds=1, status="queued", review_status="approved")

    with pytest.raises(ValueError, match="completed"):
        youtube_publisher.ensure_job_is_publishable(job)


def test_ensure_job_is_publishable_requires_approval() -> None:
    job = AudioJob(title="t", mode="sine", duration_seconds=1, status="completed", review_status="pending")

    with pytest.raises(ValueError, match="approved"):
        youtube_publisher.ensure_job_is_publishable(job)


def test_ensure_job_is_publishable_accepts_approved_completed_job() -> None:
    job = AudioJob(title="t", mode="sine", duration_seconds=1, status="completed", review_status="approved")

    assert youtube_publisher.ensure_job_is_publishable(job) is job


def test_build_authorization_url_requires_oauth_configuration(monkeypatch, db) -> None:
    monkeypatch.setattr(youtube_publisher, "get_settings", lambda: _EmptySettings())
    monkeypatch.setattr(secrets_service, "get_settings", lambda: _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        youtube_publisher.build_authorization_url("state", db=db)


def test_build_authorization_url_returns_google_oauth_url(monkeypatch, db) -> None:
    monkeypatch.setattr(youtube_publisher, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(secrets_service, "get_settings", lambda: _FakeSettings())

    url = youtube_publisher.build_authorization_url("test-state", db=db)

    assert url.startswith("https://accounts.google.com/o/oauth2/")
    assert "state=test-state" in url
    assert "client_id=test-client-id" in url


def test_fetch_channel_identity_returns_id_and_title(monkeypatch) -> None:
    fake_service = _FakeChannelsService([{"id": "UC123", "snippet": {"title": "AION Ambient"}}])
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    channel_id, channel_title = youtube_publisher.fetch_channel_identity(object())

    assert channel_id == "UC123"
    assert channel_title == "AION Ambient"


def test_fetch_channel_identity_raises_when_no_channel(monkeypatch) -> None:
    fake_service = _FakeChannelsService([])
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    with pytest.raises(ValueError, match="No YouTube channel"):
        youtube_publisher.fetch_channel_identity(object())


def test_upload_video_returns_video_id_and_url(monkeypatch, tmp_path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"fake video bytes")

    fake_service = _FakeYouTubeService({"id": "abc123"})
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)
    monkeypatch.setattr(youtube_publisher, "MediaFileUpload", lambda *a, **k: object())

    video_id, video_url = youtube_publisher.upload_video(
        object(),
        video_path=video_path,
        title="Night Rain",
        description="",
        tags=["ambient"],
        category_id="10",
        privacy_status="private",
    )

    assert video_id == "abc123"
    assert video_url == "https://www.youtube.com/watch?v=abc123"


def test_upload_video_raises_for_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        youtube_publisher.upload_video(
            object(),
            video_path=tmp_path / "missing.mp4",
            title="Night Rain",
            description="",
            tags=[],
            category_id="10",
            privacy_status="private",
        )


def test_set_video_thumbnail_calls_thumbnails_set(monkeypatch, tmp_path) -> None:
    thumbnail_path = tmp_path / "cover.png"
    thumbnail_path.write_bytes(b"fake png bytes")

    calls: list[dict] = []
    fake_service = _FakeThumbnailsService(calls)
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)
    monkeypatch.setattr(youtube_publisher, "MediaFileUpload", lambda *a, **k: object())

    youtube_publisher.set_video_thumbnail(
        object(), video_id="abc123", thumbnail_path=thumbnail_path
    )

    assert len(calls) == 1
    assert calls[0]["videoId"] == "abc123"


def test_set_video_thumbnail_raises_for_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        youtube_publisher.set_video_thumbnail(
            object(), video_id="abc123", thumbnail_path=tmp_path / "missing.png"
        )


def test_delete_video_calls_videos_delete(monkeypatch) -> None:
    delete_calls: list[str] = []
    fake_service = _FakeYouTubeService(delete_calls=delete_calls)
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    youtube_publisher.delete_video(object(), video_id="abc123")

    assert delete_calls == ["abc123"]


def test_credentials_from_stored_decrypts_tokens(monkeypatch, db) -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")

    class _EncryptionSettings:
        token_encryption_key = key

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EncryptionSettings())
    encrypted_access = token_encryption.encrypt_token("real-access-token")
    encrypted_refresh = token_encryption.encrypt_token("real-refresh-token")

    monkeypatch.setattr(youtube_publisher, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(secrets_service, "get_settings", lambda: _FakeSettings())

    record = YouTubeCredential(
        channel_id="UC123",
        access_token=encrypted_access,
        refresh_token=encrypted_refresh,
        token_expiry=None,
        scopes=youtube_publisher.SCOPES,
    )

    credentials = youtube_publisher.credentials_from_stored(record, db=db)

    assert credentials.token == "real-access-token"
    assert credentials.refresh_token == "real-refresh-token"


def test_youtube_upload_request_rejects_invalid_privacy_status() -> None:
    with pytest.raises(ValidationError):
        YouTubeUploadRequest(
            audio_job_id="11111111-1111-1111-1111-111111111111",
            video_filename="clip.mp4",
            title="Night Rain",
            privacy_status="everyone",
        )


def test_youtube_upload_request_defaults_to_private() -> None:
    request = YouTubeUploadRequest(
        audio_job_id="11111111-1111-1111-1111-111111111111",
        video_filename="clip.mp4",
        title="Night Rain",
    )

    assert request.privacy_status == "private"


def test_search_top_videos_combines_search_results_with_real_view_counts(monkeypatch) -> None:
    search_items = [
        {
            "id": {"videoId": "vid1"},
            "snippet": {"title": "432Hz Focus Music - Brown Noise", "channelTitle": "Channel A"},
        },
        {
            "id": {"videoId": "vid2"},
            "snippet": {"title": "528Hz Deep Focus - Rain Sounds", "channelTitle": "Channel B"},
        },
    ]
    stats_items = [
        {
            "id": "vid1",
            "statistics": {"viewCount": "1500000"},
            "contentDetails": {"duration": "PT10H"},
        },
        {
            "id": "vid2",
            "statistics": {"viewCount": "900000"},
            "contentDetails": {"duration": "PT1H"},
        },
    ]
    fake_service = _FakeSearchService(search_items, stats_items)
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    results = youtube_publisher.search_top_videos(object(), query="432hz focus music", max_results=10)

    assert len(results) == 2
    assert results[0]["video_id"] == "vid1"
    assert results[0]["title"] == "432Hz Focus Music - Brown Noise"
    assert results[0]["view_count"] == 1500000
    assert results[0]["duration"] == "PT10H"
    assert results[1]["view_count"] == 900000


def test_search_top_videos_returns_empty_list_for_no_results(monkeypatch) -> None:
    fake_service = _FakeSearchService([], [])
    monkeypatch.setattr(youtube_publisher, "build", lambda *a, **k: fake_service)

    results = youtube_publisher.search_top_videos(object(), query="a query with no results")

    assert results == []
