import base64
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.provider_config import require_openrouter_key
from app.services.replicate_client import create_prediction, extract_output_url, poll_until_complete
from app.services.secrets import resolve_secret

ArtworkProvider = Literal["replicate", "openrouter"]


@dataclass(frozen=True)
class ArtworkGenerationResult:
    path: Path
    # The exact cost OpenRouter's own response reported, when the provider
    # includes one. None for Replicate, whose prediction API doesn't return
    # billing data inline -- callers fall back to a documented per-call
    # estimate (settings.flux_replicate_cost_usd) for that case.
    cost_usd: float | None

_OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_POLL_TIMEOUT_SECONDS = 180.0


def aspect_ratio_for(width: int, height: int) -> str:
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _ensure_replicate_configured(db: Session) -> str:
    token = resolve_secret(db, "replicate_api_token")

    if not token:
        raise ValueError(
            "AI artwork via Replicate is not configured: set a Replicate "
            "key in Settings (or REPLICATE_API_TOKEN)."
        )

    return token


def _generate_via_replicate(
    prompt: str,
    *,
    output_path: Path,
    aspect_ratio: str,
    seed: int | None,
    db: Session,
) -> ArtworkGenerationResult:
    # Verified directly against the real model schema (GET
    # /v1/models/black-forest-labs/flux-schnell), not assumed: prompt,
    # aspect_ratio, seed, and output_format are all real input fields.
    # output_format matters specifically -- it defaults to "webp", which
    # doesn't match the ".png" extension this app always saves artwork
    # under (found via a real generated file: valid image, correct
    # content, but actually WEBP despite the .png name). Forcing "png"
    # here keeps the file's actual format honest, since other code (the
    # export bundle's suffix allowlist, eventual thumbnail uploads) will
    # eventually trust the extension.
    token = _ensure_replicate_configured(db)
    settings = get_settings()

    input_payload: dict = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
    }
    if seed is not None:
        input_payload["seed"] = seed

    with httpx.Client(timeout=30.0) as client:
        prediction = create_prediction(client, token, settings.flux_model, input_payload)
        prediction = poll_until_complete(
            client,
            token,
            prediction,
            timeout_seconds=_POLL_TIMEOUT_SECONDS,
            error_label="AI artwork generation",
        )
        image_url = extract_output_url(prediction)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_response = client.get(image_url)
        image_response.raise_for_status()
        output_path.write_bytes(image_response.content)

    return ArtworkGenerationResult(path=output_path, cost_usd=None)


def _generate_via_openrouter(
    prompt: str,
    *,
    output_path: Path,
    aspect_ratio: str,
    seed: int | None,
    db: Session,
) -> ArtworkGenerationResult:
    # Verified against OpenRouter's own docs (openrouter.ai/docs/guides/
    # overview/multimodal/image-generation) as of 2026-07: POST /v1/images,
    # response images arrive base64-encoded under data[0].b64_json. Not yet
    # exercised against a real key -- no OPENROUTER_API_KEY is configured
    # in this environment by design (kept dormant, see config.py).
    token = require_openrouter_key(db)
    settings = get_settings()

    payload: dict = {
        "model": settings.openrouter_image_model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
    }
    if seed is not None:
        payload["seed"] = seed

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(_OPENROUTER_IMAGES_URL, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()

    images = body.get("data")
    if not images or "b64_json" not in images[0]:
        raise RuntimeError(f"Unexpected OpenRouter image response shape: {body!r}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(images[0]["b64_json"]))

    cost_usd = body.get("usage", {}).get("cost")
    return ArtworkGenerationResult(path=output_path, cost_usd=cost_usd)


def generate_ai_artwork(
    prompt: str,
    *,
    output_path: Path,
    provider: ArtworkProvider,
    width: int,
    height: int,
    db: Session,
    seed: int | None = None,
) -> ArtworkGenerationResult:
    aspect_ratio = aspect_ratio_for(width, height)

    if provider == "replicate":
        return _generate_via_replicate(
            prompt, output_path=output_path, aspect_ratio=aspect_ratio, seed=seed, db=db
        )

    if provider == "openrouter":
        return _generate_via_openrouter(
            prompt, output_path=output_path, aspect_ratio=aspect_ratio, seed=seed, db=db
        )

    raise ValueError(f"Unknown AI artwork provider: {provider}")
