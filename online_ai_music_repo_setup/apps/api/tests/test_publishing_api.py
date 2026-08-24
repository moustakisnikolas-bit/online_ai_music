from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.routes import publishing
from app.db.session import SessionLocal
from app.main import app
from app.models.youtube_publishing import YouTubeCredential
from app.repositories.oauth_state import create_oauth_state

client = TestClient(app, follow_redirects=False)


def test_callback_is_a_get_request_not_a_post() -> None:
    # The real bug this route was rewritten to fix: Google always redirects
    # the browser back via GET with query params, never a POST with a JSON
    # body. A GET request with no parameters should reach the handler (and
    # redirect with a reason), not 405 or 422.
    response = client.get("/api/v1/publishing/youtube/callback")

    assert response.status_code == 307
    assert response.headers["location"] == "/app?youtube_connect=error&reason=missing_parameters"


def test_callback_redirects_with_provider_error_reason() -> None:
    response = client.get(
        "/api/v1/publishing/youtube/callback",
        params={"error": "access_denied"},
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/app?youtube_connect=error&reason=access_denied"


def test_callback_redirects_on_invalid_state() -> None:
    response = client.get(
        "/api/v1/publishing/youtube/callback",
        params={"code": "some-code", "state": "never-issued-state"},
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "/app?youtube_connect=error&reason=invalid_or_expired_state"
    )


def test_callback_exchanges_code_and_redirects_to_success(monkeypatch) -> None:
    db = SessionLocal()
    try:
        create_oauth_state(db, state="test-valid-state", purpose="youtube")
    finally:
        db.close()

    class _FakeCredentials:
        token = "access-token"
        refresh_token = "refresh-token"
        expiry = None
        scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    monkeypatch.setattr(
        publishing, "exchange_code_for_credentials", lambda code, *, db: _FakeCredentials()
    )
    monkeypatch.setattr(
        publishing, "fetch_channel_identity", lambda credentials: ("UC123", "AION Ambient")
    )

    response = client.get(
        "/api/v1/publishing/youtube/callback",
        params={"code": "real-code", "state": "test-valid-state"},
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/app?youtube_connect=success"

    # Queried by this test's own channel_id, not "whichever channel is
    # most recently connected" (get_youtube_credential's normal, correct
    # behavior for the app itself) -- this dev database is the same one a
    # real, concurrently-running AION server may be using, so a genuine
    # connection landing between this test's insert and its assertion
    # must not be able to make this test flake.
    db = SessionLocal()
    try:
        record = db.scalars(
            select(YouTubeCredential).where(YouTubeCredential.channel_id == "UC123")
        ).first()
        assert record is not None
        assert record.channel_title == "AION Ambient"
    finally:
        db.execute(delete(YouTubeCredential).where(YouTubeCredential.channel_id == "UC123"))
        db.commit()
        db.close()


def test_status_reports_has_playlist_scope_true_for_broad_scope() -> None:
    db = SessionLocal()
    try:
        db.add(
            YouTubeCredential(
                channel_id="UC-playlist-scope-test",
                channel_title="Scope Test Channel",
                access_token="enc-access",
                refresh_token="enc-refresh",
                token_expiry=None,
                scopes=["https://www.googleapis.com/auth/youtube"],
            )
        )
        db.commit()

        response = client.get("/api/v1/publishing/youtube/status")

        assert response.status_code == 200
        assert response.json()["has_playlist_scope"] is True
    finally:
        db.execute(
            delete(YouTubeCredential).where(
                YouTubeCredential.channel_id == "UC-playlist-scope-test"
            )
        )
        db.commit()
        db.close()


def test_status_reports_has_playlist_scope_false_for_legacy_scopes() -> None:
    db = SessionLocal()
    try:
        db.add(
            YouTubeCredential(
                channel_id="UC-legacy-scope-test",
                channel_title="Legacy Scope Channel",
                access_token="enc-access",
                refresh_token="enc-refresh",
                token_expiry=None,
                scopes=[
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube.readonly",
                ],
            )
        )
        db.commit()

        response = client.get("/api/v1/publishing/youtube/status")

        assert response.status_code == 200
        assert response.json()["has_playlist_scope"] is False
    finally:
        db.execute(
            delete(YouTubeCredential).where(
                YouTubeCredential.channel_id == "UC-legacy-scope-test"
            )
        )
        db.commit()
        db.close()


class _FakeCredentials:
    """A stand-in for google.oauth2.credentials.Credentials -- only
    needs a .refresh() method, since that's the only thing
    _token_is_currently_valid calls on it directly."""

    def __init__(self, *, refresh_raises: Exception | None = None) -> None:
        self._refresh_raises = refresh_raises

    def refresh(self, request) -> None:
        if self._refresh_raises is not None:
            raise self._refresh_raises


def test_status_reports_connected_false_when_token_is_actually_invalid(monkeypatch) -> None:
    # The real bug this replaced: a stored credential row existing was
    # treated as "connected" even when the refresh token had been
    # revoked/expired (invalid_grant) -- only a real, forced refresh
    # catches that, which is what this exercises.
    publishing._TOKEN_CHECK_CACHE.clear()
    invalid_grant = ValueError("invalid_grant: Token has been expired or revoked.")
    monkeypatch.setattr(
        publishing,
        "credentials_from_stored",
        lambda record, *, db: _FakeCredentials(refresh_raises=invalid_grant),
    )
    monkeypatch.setattr(publishing, "fetch_channel_identity", lambda credentials: ("id", "title"))

    db = SessionLocal()
    try:
        db.add(
            YouTubeCredential(
                channel_id="UC-dead-token-test",
                channel_title="Dead Token Channel",
                access_token="enc-access",
                refresh_token="enc-refresh",
                token_expiry=None,
                scopes=["https://www.googleapis.com/auth/youtube"],
            )
        )
        db.commit()

        response = client.get("/api/v1/publishing/youtube/status")

        assert response.status_code == 200
        assert response.json()["connected"] is False
    finally:
        db.execute(delete(YouTubeCredential).where(YouTubeCredential.channel_id == "UC-dead-token-test"))
        db.commit()
        db.close()


def test_status_reports_connected_true_when_token_actually_works(monkeypatch) -> None:
    publishing._TOKEN_CHECK_CACHE.clear()
    monkeypatch.setattr(publishing, "credentials_from_stored", lambda record, *, db: _FakeCredentials())
    monkeypatch.setattr(
        publishing, "fetch_channel_identity", lambda credentials: ("UC-live-token-test", "Live Channel")
    )

    db = SessionLocal()
    try:
        db.add(
            YouTubeCredential(
                channel_id="UC-live-token-test",
                channel_title="Live Channel",
                access_token="enc-access",
                refresh_token="enc-refresh",
                token_expiry=None,
                scopes=["https://www.googleapis.com/auth/youtube"],
            )
        )
        db.commit()

        response = client.get("/api/v1/publishing/youtube/status")

        assert response.status_code == 200
        assert response.json()["connected"] is True
    finally:
        db.execute(delete(YouTubeCredential).where(YouTubeCredential.channel_id == "UC-live-token-test"))
        db.commit()
        db.close()


def test_status_caches_the_live_check_within_ttl(monkeypatch) -> None:
    publishing._TOKEN_CHECK_CACHE.clear()
    monkeypatch.setattr(publishing, "credentials_from_stored", lambda record, *, db: _FakeCredentials())

    call_count = {"n": 0}

    def _counting_fetch(credentials):
        call_count["n"] += 1
        return ("UC-cache-test", "Cache Test Channel")

    monkeypatch.setattr(publishing, "fetch_channel_identity", _counting_fetch)

    db = SessionLocal()
    try:
        db.add(
            YouTubeCredential(
                channel_id="UC-cache-test",
                channel_title="Cache Test Channel",
                access_token="enc-access",
                refresh_token="enc-refresh",
                token_expiry=None,
                scopes=["https://www.googleapis.com/auth/youtube"],
            )
        )
        db.commit()

        client.get("/api/v1/publishing/youtube/status")
        client.get("/api/v1/publishing/youtube/status")

        assert call_count["n"] == 1
    finally:
        db.execute(delete(YouTubeCredential).where(YouTubeCredential.channel_id == "UC-cache-test"))
        db.commit()
        db.close()


def test_quota_status_endpoint_returns_expected_shape(monkeypatch) -> None:
    from datetime import date as date_cls

    monkeypatch.setattr(publishing, "remaining_quota_today", lambda db, *, budget: 8400)
    monkeypatch.setattr(
        publishing,
        "get_or_create_today_usage",
        lambda db: type("Row", (), {"units_used": 1600})(),
    )
    monkeypatch.setattr(publishing, "today_pacific", lambda: date_cls(2026, 7, 30))

    response = client.get("/api/v1/publishing/youtube/quota")

    assert response.status_code == 200
    body = response.json()
    assert body["units_used"] == 1600
    assert body["daily_budget"] == 10000
    assert body["remaining"] == 8400
    assert body["uploads_remaining_today"] == (8400 - 800) // 1600
    assert body["resets_at"].startswith("2026-07-31")
