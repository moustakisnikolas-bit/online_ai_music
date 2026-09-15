import httpx
import pytest

from app.services import replicate_client
from app.services.replicate_client import _raise_for_status_with_detail, poll_until_complete


def _response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://api.replicate.com/v1/models/x/predictions")
    return httpx.Response(status_code, request=request, json=json_body)


def _get_response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.replicate.com/v1/predictions/abc")
    return httpx.Response(status_code, request=request, json=json_body)


class _FakeClient:
    """Fake httpx.Client that returns queued responses for .get() in order."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)

    def get(self, *_args, **_kwargs) -> httpx.Response:
        return self._responses.pop(0)


def test_raise_for_status_with_detail_includes_replicate_error_body() -> None:
    # Regression test: a real 402 from Replicate ("Insufficient credit")
    # was only surfaced as the generic "402 Payment Required for url ..."
    # -- the actually useful part (why, and what to do about it) lives in
    # the response body, which plain raise_for_status() discards.
    response = _response(
        402,
        {
            "title": "Insufficient credit",
            "detail": "You have insufficient credit to run this model.",
            "status": 402,
        },
    )

    with pytest.raises(httpx.HTTPStatusError, match="You have insufficient credit"):
        _raise_for_status_with_detail(response)


def test_raise_for_status_with_detail_falls_back_when_body_has_no_detail() -> None:
    response = _response(500, {"unexpected": "shape"})

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        _raise_for_status_with_detail(response)

    assert "500" in str(exc_info.value)


def test_raise_for_status_with_detail_falls_back_when_body_is_not_json() -> None:
    request = httpx.Request("POST", "https://api.replicate.com/v1/models/x/predictions")
    response = httpx.Response(503, request=request, text="<html>Bad Gateway</html>")

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        _raise_for_status_with_detail(response)

    assert "503" in str(exc_info.value)


def test_raise_for_status_with_detail_is_a_no_op_for_success() -> None:
    response = _response(200, {"status": "succeeded"})

    _raise_for_status_with_detail(response)


def test_poll_until_complete_survives_a_transient_503_mid_poll(monkeypatch) -> None:
    # Regression test for a real incident: Replicate's status-poll GET
    # returned a single 503 mid-generation while the prediction itself
    # (confirmed via a direct create call) was healthy. Before this retry
    # existed, that one blip hard-failed the whole track.
    monkeypatch.setattr(replicate_client.time, "sleep", lambda _seconds: None)

    prediction = {"status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}
    client = _FakeClient(
        [
            _get_response(503),
            _get_response(200, {"status": "processing"}),
            _get_response(200, {"status": "succeeded", "output": ["https://example.com/out.png"]}),
        ]
    )

    result = poll_until_complete(
        client, "fake-token", prediction, timeout_seconds=60.0, error_label="test"
    )

    assert result["status"] == "succeeded"


def test_poll_until_complete_gives_up_after_too_many_transient_errors(monkeypatch) -> None:
    monkeypatch.setattr(replicate_client.time, "sleep", lambda _seconds: None)

    prediction = {"status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}
    # One more 503 than the retry budget allows -- should eventually raise
    # instead of retrying forever.
    client = _FakeClient([_get_response(503)] * (replicate_client._MAX_TRANSIENT_POLL_RETRIES + 1))

    with pytest.raises(httpx.HTTPStatusError):
        poll_until_complete(client, "fake-token", prediction, timeout_seconds=60.0, error_label="test")


def test_poll_until_complete_does_not_retry_non_transient_errors(monkeypatch) -> None:
    monkeypatch.setattr(replicate_client.time, "sleep", lambda _seconds: None)

    prediction = {"status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}
    # A 402 (insufficient credit) won't fix itself on retry -- should raise
    # immediately, not burn through the transient-retry budget.
    client = _FakeClient([_get_response(402, {"title": "Insufficient credit"})])

    with pytest.raises(httpx.HTTPStatusError, match="Insufficient credit"):
        poll_until_complete(client, "fake-token", prediction, timeout_seconds=60.0, error_label="test")
