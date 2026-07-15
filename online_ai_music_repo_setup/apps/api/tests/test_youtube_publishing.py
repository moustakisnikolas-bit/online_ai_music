import pytest
from pydantic import ValidationError

from app.models.audio_job import AudioJob
from app.schemas.publishing import YouTubeCallbackRequest, YouTubeUploadRequest
from app.services import youtube_publisher


class _FakeSettings:
    youtube_client_id = "test-client-id"
    youtube_client_secret = "test-client-secret"
    youtube_redirect_uri = "http://localhost:8000/api/v1/publishing/youtube/callback"


class _EmptySettings:
    youtube_client_id = ""
    youtube_client_secret = ""
    youtube_redirect_uri = "http://localhost:8000/api/v1/publishing/youtube/callback"


class _FakeInsertRequest:
    def __init__(self, response: dict) -> None:
        self._response = response

    def next_chunk(self):
        return None, self._response


class _FakeVideosResource:
    def __init__(self, response: dict) -> None:
        self._response = response

    def insert(self, **_kwargs):
        return _FakeInsertRequest(self._response)


class _FakeYouTubeService:
    def __init__(self, response: dict) -> None:
        self._response = response

    def videos(self):
        return _FakeVideosResource(self._response)


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


def test_build_authorization_url_requires_oauth_configuration(monkeypatch) -> None:
    monkeypatch.setattr(youtube_publisher, "get_settings", lambda: _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        youtube_publisher.build_authorization_url("state")


def test_build_authorization_url_returns_google_oauth_url(monkeypatch) -> None:
    monkeypatch.setattr(youtube_publisher, "get_settings", lambda: _FakeSettings())

    url = youtube_publisher.build_authorization_url("test-state")

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


def test_youtube_callback_request_requires_code_and_state() -> None:
    with pytest.raises(ValidationError):
        YouTubeCallbackRequest(code="", state="")
