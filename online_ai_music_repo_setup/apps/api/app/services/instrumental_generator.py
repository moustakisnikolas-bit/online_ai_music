import time
from pathlib import Path

import httpx

from app.core.config import get_settings

_REPLICATE_API_BASE = "https://api.replicate.com/v1"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
_POLL_INTERVAL_SECONDS = 2.0
_POLL_TIMEOUT_SECONDS = 300.0


def _ensure_configured() -> str:
    settings = get_settings()

    if not settings.replicate_api_token:
        raise ValueError(
            "Instrumental generation is not configured: set REPLICATE_API_TOKEN."
        )

    return settings.replicate_api_token


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _create_prediction(
    client: httpx.Client,
    token: str,
    model: str,
    prompt: str,
    duration_seconds: float,
    seed: int | None,
) -> dict:
    # Input field names (prompt, seconds_total, seed) follow Stable Audio
    # Open's typical inference interface, but this is a community-hosted
    # model on Replicate (not an "official" model with a stable schema
    # guarantee) -- verify against the model's actual Replicate page
    # (replicate.com/stackadoc/stable-audio-open-1.0) before first real use
    # and adjust field names here if they differ. Not verifiable without a
    # Replicate account/API token, which this environment doesn't have.
    payload = {
        "input": {
            "prompt": prompt,
            "seconds_total": duration_seconds,
        }
    }

    if seed is not None:
        payload["input"]["seed"] = seed

    response = client.post(
        f"{_REPLICATE_API_BASE}/models/{model}/predictions",
        headers=_headers(token),
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def _poll_until_complete(client: httpx.Client, token: str, prediction: dict) -> dict:
    get_url = prediction["urls"]["get"]
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    while prediction.get("status") not in _TERMINAL_STATUSES:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Instrumental generation timed out after {_POLL_TIMEOUT_SECONDS:.0f}s"
            )

        time.sleep(_POLL_INTERVAL_SECONDS)
        response = client.get(get_url, headers=_headers(token))
        response.raise_for_status()
        prediction = response.json()

    if prediction["status"] != "succeeded":
        raise RuntimeError(
            f"Instrumental generation failed: {prediction.get('error') or prediction['status']}"
        )

    return prediction


def _extract_output_url(prediction: dict) -> str:
    output = prediction.get("output")

    if isinstance(output, list) and output:
        return output[0]

    if isinstance(output, str):
        return output

    raise RuntimeError(f"Unexpected prediction output shape: {output!r}")


def generate_instrumental_clip(
    prompt: str,
    *,
    duration_seconds: float,
    output_path: Path,
    seed: int | None = None,
) -> Path:
    token = _ensure_configured()
    settings = get_settings()

    with httpx.Client(timeout=30.0) as client:
        prediction = _create_prediction(
            client, token, settings.stable_audio_model, prompt, duration_seconds, seed
        )
        prediction = _poll_until_complete(client, token, prediction)
        audio_url = _extract_output_url(prediction)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_response = client.get(audio_url)
        audio_response.raise_for_status()
        output_path.write_bytes(audio_response.content)

    return output_path
