import re
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.services.secrets import resolve_secret

_UPLOAD_TIMEOUT_SECONDS = 300.0


def ensure_configured(db: Session) -> tuple[str, str]:
    access_key = resolve_secret(db, "internet_archive_access_key")
    secret_key = resolve_secret(db, "internet_archive_secret_key")

    if not access_key or not secret_key:
        raise ValueError(
            "Internet Archive publishing is not configured: set an access "
            "key and secret key in Settings (get a pair from "
            "archive.org/account/s3.php), or INTERNET_ARCHIVE_ACCESS_KEY / "
            "INTERNET_ARCHIVE_SECRET_KEY."
        )

    return access_key, secret_key


def build_item_identifier(title: str, audio_job_id: uuid.UUID) -> str:
    # Archive.org item identifiers must be globally unique across the
    # entire archive and are restricted to alphanumerics, underscore,
    # hyphen, and period -- no spaces. Appending a slice of the job's own
    # UUID (already unique within this app) makes a collision with an
    # unrelated existing archive.org item astronomically unlikely without
    # needing to check first.
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "aion-track"
    return f"{slug}-{str(audio_job_id)[:8]}"[:100]


def upload_track(
    *,
    access_key: str,
    secret_key: str,
    item_identifier: str,
    audio_path: Path,
    title: str,
    description: str = "",
    creator: str | None = None,
    license_url: str | None = None,
) -> str:
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    headers = {
        "Authorization": f"LOW {access_key}:{secret_key}",
        "x-archive-auto-make-bucket": "1",
        "x-archive-meta-mediatype": "audio",
        "x-archive-meta-collection": "opensource_audio",
        "x-archive-meta-title": title,
    }
    if description:
        headers["x-archive-meta-description"] = description
    if creator:
        headers["x-archive-meta-creator"] = creator
    if license_url:
        headers["x-archive-meta-licenseurl"] = license_url

    upload_url = f"https://s3.us.archive.org/{item_identifier}/{audio_path.name}"

    with httpx.Client(timeout=_UPLOAD_TIMEOUT_SECONDS) as client:
        with audio_path.open("rb") as file_handle:
            response = client.put(upload_url, headers=headers, content=file_handle)
        response.raise_for_status()

    return f"https://archive.org/details/{item_identifier}"
