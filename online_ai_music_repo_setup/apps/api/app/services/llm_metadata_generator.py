import json

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.metadata_generator import (
    COMPLIANCE_NOTE,
    SAFE_CONTEXT_LABELS,
    MetadataPackage,
    clean_text,
)
from app.services.provider_config import require_openrouter_key

_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def _build_prompt(
    *,
    source_title: str,
    mode: str,
    duration_seconds: int,
    context: str,
    frequency_hz: float | None,
    texture_mode: str | None,
) -> str:
    duration_minutes = max(1, round(duration_seconds / 60))
    details = [mode.replace("_", " ")]

    if frequency_hz is not None:
        details.append(f"{frequency_hz:g} Hz")

    if texture_mode and texture_mode != "none":
        details.append(texture_mode.replace("_", " "))

    return (
        "Write YouTube-ready metadata for a therapeutic ambient audio track. "
        f"Source title: {source_title!r}. Category: {context}. "
        f"Duration: ~{duration_minutes} minutes. Sound design: {', '.join(details)}. "
        "This is NOT medical treatment and must not be described as one -- "
        "no disease claims, no guaranteed therapeutic outcomes. "
        "Respond with ONLY a JSON object with exactly these keys: "
        '"title" (string, catchy, under 100 chars), '
        '"subtitle" (string, under 100 chars), '
        '"description" (string, 300-400 characters, written to intrigue '
        "someone scrolling past into clicking play -- a real hook, not "
        "generic filler), "
        '"keywords" (array of 5-10 lowercase strings). '
        "No markdown, no code fences, no explanation -- JSON only."
    )


def generate_llm_metadata_package(
    *,
    source_title: str,
    mode: str,
    duration_seconds: int,
    db: Session,
    context: str = "ambient",
    language: str = "en",
    frequency_hz: float | None = None,
    texture_mode: str | None = None,
) -> tuple[MetadataPackage, float | None]:
    token = require_openrouter_key(db)
    settings = get_settings()

    prompt = _build_prompt(
        source_title=source_title,
        mode=mode,
        duration_seconds=duration_seconds,
        context=context,
        frequency_hz=frequency_hz,
        texture_mode=texture_mode,
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openrouter_text_model,
        "messages": [{"role": "user", "content": prompt}],
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(_CHAT_COMPLETIONS_URL, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        title = str(parsed["title"])
        subtitle = str(parsed["subtitle"])
        description = str(parsed["description"])
        keywords = [str(keyword) for keyword in parsed["keywords"]]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unexpected LLM metadata response shape: {body!r}") from exc

    cost_usd = body.get("usage", {}).get("cost")

    # The compliance note is never LLM-generated -- safety-critical
    # language stays deterministic and identical to the template
    # generator's, consistent with the compliance-first principle. Only
    # the creative fields (title/subtitle/description/keywords) come from
    # the model.
    package = MetadataPackage(
        title=clean_text(title),
        subtitle=clean_text(subtitle),
        description=clean_text(description),
        keywords=sorted(set(keyword.lower() for keyword in keywords)),
        category=SAFE_CONTEXT_LABELS.get(context, "Ambient"),
        language=language,
        compliance_note=COMPLIANCE_NOTE,
    )

    return package, cost_usd
