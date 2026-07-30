from sqlalchemy.orm import Session

from app.services.secrets import resolve_secret


def require_openrouter_key(db: Session) -> str:
    key = resolve_secret(db, "openrouter_api_key")

    if not key:
        raise ValueError(
            "OpenRouter is not configured: set an OpenRouter key in "
            "Settings (or OPENROUTER_API_KEY). This provider is "
            "intentionally left dormant until you're ready to use it."
        )

    return key
