from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.youtube_publishing import YouTubeQuotaUsage
from app.repositories import youtube_quota
from app.repositories.youtube_quota import (
    get_or_create_today_usage,
    record_quota_usage,
    remaining_quota_today,
    today_pacific,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[YouTubeQuotaUsage.__table__])

    with Session(engine) as session:
        yield session


def test_today_pacific_returns_a_real_date() -> None:
    assert isinstance(today_pacific(), date)


def test_get_or_create_today_usage_starts_at_zero(db) -> None:
    row = get_or_create_today_usage(db)
    assert row.units_used == 0


def test_get_or_create_today_usage_is_idempotent(db) -> None:
    first = get_or_create_today_usage(db)
    second = get_or_create_today_usage(db)
    assert first.id == second.id


def test_record_quota_usage_increments_across_calls(db) -> None:
    record_quota_usage(db, units=1600)
    row = record_quota_usage(db, units=1600)

    assert row.units_used == 3200


def test_remaining_quota_today_subtracts_usage(db) -> None:
    record_quota_usage(db, units=1600)

    assert remaining_quota_today(db, budget=10000) == 8400


def test_remaining_quota_today_floors_at_zero(db) -> None:
    record_quota_usage(db, units=15000)

    assert remaining_quota_today(db, budget=10000) == 0


def test_rollover_creates_a_separate_row_for_a_new_pacific_day(monkeypatch, db) -> None:
    dates = iter([date(2026, 7, 29), date(2026, 7, 29), date(2026, 7, 30)])
    monkeypatch.setattr(youtube_quota, "today_pacific", lambda: next(dates))

    first_day_row = record_quota_usage(db, units=1600)
    same_day_row = record_quota_usage(db, units=1600)
    next_day_row = record_quota_usage(db, units=1600)

    assert first_day_row.id == same_day_row.id
    assert same_day_row.units_used == 3200
    assert next_day_row.id != first_day_row.id
    assert next_day_row.units_used == 1600
