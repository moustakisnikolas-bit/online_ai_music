import httpx
import pytest

from app.services.replicate_client import _raise_for_status_with_detail


def _response(status_code: int, json_body: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://api.replicate.com/v1/models/x/predictions")
    return httpx.Response(status_code, request=request, json=json_body)


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
