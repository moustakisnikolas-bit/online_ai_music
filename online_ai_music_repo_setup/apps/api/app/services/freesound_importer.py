import io
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from sqlalchemy.orm import Session

from app.audio.sample_library import (
    MANIFEST_PATH,
    SAMPLE_LIBRARY_DIR,
    NaturalSoundSample,
    register_sample,
)
from app.schemas.sample import FreesoundSearchResultItem
from app.services.secrets import resolve_secret

# The only license this product may use commercially -- see
# docs/06-factories/natural-sound-sample-library.md. Not CC-BY (requires
# attribution tracking we don't yet do for imports) and not CC-BY-NC
# (forbids commercial use outright).
_CC0_LICENSE = "Creative Commons 0"

# Freesound's docs describe the license field as the plain string above,
# and that's what the search filter syntax (license:"Creative Commons 0")
# expects -- but real API responses were found (empirically, via an actual
# batch import) to return the license on GET /sounds/<id>/ as this
# Creative Commons URL instead, not the plain string. Accept both rather
# than trust the docs alone -- a mismatch here fails every real import
# closed (refuses to import), so a real live sound was needed to catch it.
_CC0_LICENSE_VALUES = frozenset(
    {
        _CC0_LICENSE,
        "http://creativecommons.org/publicdomain/zero/1.0/",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    }
)

_SEARCH_FIELDS = "id,name,license,previews,username,url"
_API_BASE = "https://freesound.org/apiv2"

# Preview files are compressed but can still be several/tens of MB for
# longer field recordings (ambience/nature clips run much longer than
# short SFX), and CDN throughput varies a lot by network -- 30s (the
# original value) turned out too tight even on a merely mediocre
# connection during a real bulk import, where downloads were still
# actively progressing well past that. This is a request-level timeout
# (resets on each chunk received, per httpx's default semantics), so a
# larger value only matters for genuinely slow-but-progressing transfers,
# not stuck ones.
_DOWNLOAD_TIMEOUT_SECONDS = 180.0


def _ensure_configured(db: Session) -> str:
    key = resolve_secret(db, "freesound_api_key")

    if not key:
        raise ValueError(
            "Freesound import is not configured: set a Freesound API key "
            "in Settings (or FREESOUND_API_KEY)."
        )

    return key


def search_cc0_sounds(
    query: str,
    *,
    db: Session,
    page_size: int = 15,
) -> list[FreesoundSearchResultItem]:
    api_key = _ensure_configured(db)

    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"{_API_BASE}/search/text/",
            headers={"Authorization": f"Token {api_key}"},
            params={
                "query": query,
                "filter": f'license:"{_CC0_LICENSE}"',
                "fields": _SEARCH_FIELDS,
                "page_size": page_size,
            },
        )
        response.raise_for_status()
        payload = response.json()

    return [
        FreesoundSearchResultItem(
            freesound_id=result["id"],
            name=result["name"],
            license=result["license"],
            preview_url=result["previews"]["preview-hq-ogg"],
            username=result["username"],
            page_url=result["url"],
        )
        for result in payload.get("results", [])
    ]


def import_sample_from_freesound(
    freesound_id: int,
    *,
    sample_id: str,
    label: str,
    category: str,
    db: Session,
    library_dir: Path = SAMPLE_LIBRARY_DIR,
    manifest_path: Path = MANIFEST_PATH,
    # "preview-hq-ogg" (~192kbps, the default) or "preview-lq-ogg"
    # (~80kbps) -- an escape hatch for bandwidth-constrained situations,
    # since these are already-compressed previews and a lower-bitrate one
    # is still a perfectly usable ambient texture bed.
    preview_key: str = "preview-hq-ogg",
    # Field recordings on Freesound are often long (some run 15-30+
    # minutes) -- decoded to raw 16-bit PCM WAV that's tens to hundreds of
    # MB for a sample library entry that only ever gets looped anyway
    # (load_sample_layer tiles it to fill the requested duration). Capped
    # by default; pass None for no cap.
    max_duration_seconds: float | None = 120.0,
) -> NaturalSoundSample:
    api_key = _ensure_configured(db)
    headers = {"Authorization": f"Token {api_key}"}

    with httpx.Client(timeout=_DOWNLOAD_TIMEOUT_SECONDS) as client:
        detail_response = client.get(
            f"{_API_BASE}/sounds/{freesound_id}/",
            headers=headers,
            params={"fields": _SEARCH_FIELDS},
        )
        detail_response.raise_for_status()
        detail = detail_response.json()

        # Defense in depth: the search filter can be stale by the time a
        # human picks a result, so the license is re-verified here, on the
        # specific sound, right before it's downloaded and registered --
        # not just trusted from the earlier search response.
        if detail["license"] not in _CC0_LICENSE_VALUES:
            raise ValueError(
                f"Sound {freesound_id} is licensed {detail['license']!r}, "
                "which is not a recognized CC0 value -- refusing to "
                "import a non-CC0 sound."
            )

        preview_url = detail["previews"][preview_key]
        audio_response = client.get(preview_url, headers=headers)
        audio_response.raise_for_status()

    # Freesound previews are compressed OGG, not the pristine original --
    # decode and re-encode as 16-bit PCM WAV so load_sample_layer (which
    # only reads via stdlib `wave`) needs no changes.
    samples, source_rate = sf.read(io.BytesIO(audio_response.content), dtype="float32")

    if max_duration_seconds is not None:
        max_frames = int(max_duration_seconds * source_rate)
        samples = samples[:max_frames]

    filename = f"{sample_id}.wav"
    output_path = library_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), np.clip(samples, -1.0, 1.0), source_rate, subtype="PCM_16")

    sample = NaturalSoundSample(
        id=sample_id,
        label=label,
        category=category,
        filename=filename,
        license=f"{_CC0_LICENSE} (CC0) via Freesound",
        source_url=f"https://freesound.org/s/{freesound_id}/",
        attribution=None,
        source_type="freesound",
    )
    register_sample(sample, manifest_path)

    return sample
