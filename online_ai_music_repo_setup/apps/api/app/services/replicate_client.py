import time

import httpx

_REPLICATE_API_BASE = "https://api.replicate.com/v1"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
_POLL_INTERVAL_SECONDS = 2.0
# Replicate's own infra occasionally 503s a single status-poll GET even
# while the prediction itself is running fine and Replicate is otherwise
# healthy (confirmed via a direct test call during a real incident: create
# returned 201, but one poll among ~30 mid-generation returned 503). Before
# this retry existed, that one blip hard-failed the whole track and needed
# a manual DB recovery. Only these transient, infra-level codes are worth
# retrying -- a 4xx (bad input, insufficient credit, auth) won't fix itself.
_TRANSIENT_POLL_STATUS_CODES = {502, 503, 504}
_MAX_TRANSIENT_POLL_RETRIES = 5


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _raise_for_status_with_detail(response: httpx.Response) -> None:
    # Plain raise_for_status() only reports the generic status line (e.g.
    # "402 Payment Required for url ...") and silently discards the
    # response body -- which is where Replicate actually puts the useful
    # part ({"title": "Insufficient credit", "detail": "..."}). Without
    # this, diagnosing a real failure meant manually re-running the same
    # call outside the app just to see the body. Falls back to the plain
    # message if the body isn't the expected JSON shape.
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            body = response.json()
            detail = body.get("detail") or body.get("title")
        except ValueError:
            detail = None

        message = str(exc)
        if detail:
            message = f"{message} -- {detail}"

        raise httpx.HTTPStatusError(
            message, request=exc.request, response=exc.response
        ) from exc


def create_prediction(
    client: httpx.Client,
    token: str,
    model: str,
    input_payload: dict,
) -> dict:
    response = client.post(
        f"{_REPLICATE_API_BASE}/models/{model}/predictions",
        headers=headers(token),
        json={"input": input_payload},
    )
    _raise_for_status_with_detail(response)
    return response.json()


def poll_until_complete(
    client: httpx.Client,
    token: str,
    prediction: dict,
    *,
    timeout_seconds: float,
    error_label: str,
) -> dict:
    get_url = prediction["urls"]["get"]
    deadline = time.monotonic() + timeout_seconds
    transient_retries = 0

    while prediction.get("status") not in _TERMINAL_STATUSES:
        if time.monotonic() > deadline:
            raise TimeoutError(f"{error_label} timed out after {timeout_seconds:.0f}s")

        time.sleep(_POLL_INTERVAL_SECONDS)
        response = client.get(get_url, headers=headers(token))

        if response.status_code in _TRANSIENT_POLL_STATUS_CODES:
            transient_retries += 1
            if transient_retries > _MAX_TRANSIENT_POLL_RETRIES:
                _raise_for_status_with_detail(response)
            continue  # don't touch `prediction` -- retry the same poll next loop

        _raise_for_status_with_detail(response)
        prediction = response.json()
        transient_retries = 0

    if prediction["status"] != "succeeded":
        raise RuntimeError(
            f"{error_label} failed: {prediction.get('error') or prediction['status']}"
        )

    return prediction


def extract_output_url(prediction: dict) -> str:
    output = prediction.get("output")

    if isinstance(output, list) and output:
        return output[0]

    if isinstance(output, str):
        return output

    raise RuntimeError(f"Unexpected prediction output shape: {output!r}")
