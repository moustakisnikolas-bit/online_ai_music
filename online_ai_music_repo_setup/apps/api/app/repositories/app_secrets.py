from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_secret import AppSecret
from app.services.token_encryption import decrypt_token, encrypt_token

# The only keys this repository will read/write. Anything else is
# rejected -- there's no reason for arbitrary key names to reach the
# database, and this doubles as the list the Settings page/API iterate
# over.
MANAGED_SECRET_KEYS = (
    "youtube_client_id",
    "youtube_client_secret",
    "replicate_api_token",
    "openrouter_api_key",
    "freesound_api_key",
    "internet_archive_access_key",
    "internet_archive_secret_key",
)


def _require_managed_key(key: str) -> None:
    if key not in MANAGED_SECRET_KEYS:
        raise ValueError(f"Unknown secret key: {key!r}")


def set_secret(db: Session, *, key: str, value: str) -> AppSecret:
    _require_managed_key(key)

    record = db.scalars(select(AppSecret).where(AppSecret.key == key)).first()

    if record is None:
        record = AppSecret(key=key, value_encrypted=encrypt_token(value))
        db.add(record)
    else:
        record.value_encrypted = encrypt_token(value)

    db.commit()
    db.refresh(record)
    return record


def delete_secret(db: Session, *, key: str) -> bool:
    _require_managed_key(key)

    record = db.scalars(select(AppSecret).where(AppSecret.key == key)).first()

    if record is None:
        return False

    db.delete(record)
    db.commit()
    return True


def get_secret_value(db: Session, key: str) -> str | None:
    """Decrypted value for internal use only -- never return this over HTTP."""
    _require_managed_key(key)

    record = db.scalars(select(AppSecret).where(AppSecret.key == key)).first()

    if record is None:
        return None

    return decrypt_token(record.value_encrypted)


def is_secret_overridden(db: Session, key: str) -> bool:
    _require_managed_key(key)

    return (
        db.scalars(select(AppSecret.id).where(AppSecret.key == key)).first()
        is not None
    )
