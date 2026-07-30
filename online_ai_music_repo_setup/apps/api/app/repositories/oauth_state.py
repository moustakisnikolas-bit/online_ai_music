from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.oauth_state import OAuthState

_DEFAULT_TTL_SECONDS = 600


def create_oauth_state(
    db: Session,
    *,
    state: str,
    purpose: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> OAuthState:
    record = OAuthState(
        state=state,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    db.add(record)
    db.commit()
    return record


def consume_oauth_state(db: Session, *, state: str, purpose: str) -> bool:
    """Look up a single-use state token and delete it if valid.

    Returns True only if a matching, unexpired, correct-purpose row existed.
    The row is deleted either way it's found (used or expired), so a given
    state string can never be replayed.
    """
    record = db.scalars(select(OAuthState).where(OAuthState.state == state)).first()

    if record is None:
        return False

    db.execute(delete(OAuthState).where(OAuthState.state == state))
    db.commit()

    if record.purpose != purpose:
        return False

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        # Some backends (e.g. SQLite, used in tests) don't round-trip
        # timezone-aware datetimes; the column is always written in UTC,
        # so a naive read-back can be safely assumed to be UTC too.
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        return False

    return True
