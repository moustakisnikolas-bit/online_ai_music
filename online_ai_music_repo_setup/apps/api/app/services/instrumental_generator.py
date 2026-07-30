from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.replicate_client import create_prediction, extract_output_url, poll_until_complete
from app.services.secrets import resolve_secret

_POLL_TIMEOUT_SECONDS = 300.0


def _ensure_configured(db: Session) -> str:
    token = resolve_secret(db, "replicate_api_token")

    if not token:
        raise ValueError(
            "Instrumental generation is not configured: set a Replicate "
            "key in Settings (or REPLICATE_API_TOKEN)."
        )

    return token


def generate_instrumental_clip(
    prompt: str,
    *,
    duration_seconds: float,
    output_path: Path,
    db: Session,
    seed: int | None = None,
) -> Path:
    # Input field names (prompt, seconds_total, seed) follow Stable Audio
    # Open's typical inference interface, but this is a community-hosted
    # model on Replicate (not an "official" model with a stable schema
    # guarantee) -- verify against the model's actual Replicate page
    # (replicate.com/stackadoc/stable-audio-open-1.0) before first real use
    # and adjust field names here if they differ. Not verifiable without a
    # Replicate account/API token, which this environment doesn't have.
    token = _ensure_configured(db)
    settings = get_settings()

    input_payload: dict = {"prompt": prompt, "seconds_total": duration_seconds}
    if seed is not None:
        input_payload["seed"] = seed

    with httpx.Client(timeout=30.0) as client:
        prediction = create_prediction(client, token, settings.stable_audio_model, input_payload)
        prediction = poll_until_complete(
            client,
            token,
            prediction,
            timeout_seconds=_POLL_TIMEOUT_SECONDS,
            error_label="Instrumental generation",
        )
        audio_url = extract_output_url(prediction)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_response = client.get(audio_url)
        audio_response.raise_for_status()
        output_path.write_bytes(audio_response.content)

    return output_path
