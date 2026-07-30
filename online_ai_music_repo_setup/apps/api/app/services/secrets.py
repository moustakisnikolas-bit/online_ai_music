from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.app_secrets import (
    MANAGED_SECRET_KEYS,
    get_secret_value,
    is_secret_overridden,
)


def resolve_secret(db: Session, key: str) -> str:
    """DB-stored override (saved through the Settings page) if present and
    non-empty, else the .env-based Settings value. No caching of its own --
    a value saved through the UI takes effect on the very next call, unlike
    get_settings()'s @lru_cache, which stays untouched for every other
    (non-secret) field.
    """
    override = get_secret_value(db, key)

    if override:
        return override

    return getattr(get_settings(), key)


def secret_status(db: Session, key: str) -> dict:
    if is_secret_overridden(db, key):
        source = "database"
        configured = True
    elif getattr(get_settings(), key):
        source = "environment"
        configured = True
    else:
        source = "unconfigured"
        configured = False

    return {"key": key, "configured": configured, "source": source}


def all_secret_statuses(db: Session) -> list[dict]:
    return [secret_status(db, key) for key in MANAGED_SECRET_KEYS]
