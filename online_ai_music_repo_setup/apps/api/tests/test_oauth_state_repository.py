from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.oauth_state import OAuthState
from app.repositories.oauth_state import consume_oauth_state, create_oauth_state


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[OAuthState.__table__])
    with Session(engine) as session:
        yield session


def test_create_then_consume_succeeds(db: Session) -> None:
    create_oauth_state(db, state="abc123", purpose="youtube")

    assert consume_oauth_state(db, state="abc123", purpose="youtube") is True


def test_consuming_twice_fails_the_second_time(db: Session) -> None:
    create_oauth_state(db, state="abc123", purpose="youtube")

    assert consume_oauth_state(db, state="abc123", purpose="youtube") is True
    assert consume_oauth_state(db, state="abc123", purpose="youtube") is False


def test_unknown_state_fails(db: Session) -> None:
    assert consume_oauth_state(db, state="never-issued", purpose="youtube") is False


def test_wrong_purpose_fails_and_still_consumes(db: Session) -> None:
    create_oauth_state(db, state="abc123", purpose="youtube")

    assert consume_oauth_state(db, state="abc123", purpose="spotify") is False
    # Consumed regardless of purpose mismatch, so it can't be replayed with
    # the correct purpose afterward either.
    assert consume_oauth_state(db, state="abc123", purpose="youtube") is False


def test_expired_state_fails(db: Session) -> None:
    record = OAuthState(
        state="abc123",
        purpose="youtube",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db.add(record)
    db.commit()

    assert consume_oauth_state(db, state="abc123", purpose="youtube") is False
