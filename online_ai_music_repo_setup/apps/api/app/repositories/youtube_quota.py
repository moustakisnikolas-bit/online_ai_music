from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.youtube_publishing import YouTubeQuotaUsage

# YouTube's Data API v3 quota resets at Pacific midnight, not UTC -- using
# the wrong timezone here would desync the pacer from Google's real reset
# schedule by up to 8 hours.
_PACIFIC = ZoneInfo("America/Los_Angeles")


def today_pacific() -> date:
    return datetime.now(_PACIFIC).date()


def get_or_create_today_usage(db: Session) -> YouTubeQuotaUsage:
    today = today_pacific()
    row = db.scalars(
        select(YouTubeQuotaUsage).where(YouTubeQuotaUsage.usage_date == today)
    ).first()

    if row is None:
        row = YouTubeQuotaUsage(usage_date=today, units_used=0)
        db.add(row)
        db.commit()
        db.refresh(row)

    return row


def record_quota_usage(db: Session, *, units: int) -> YouTubeQuotaUsage:
    row = get_or_create_today_usage(db)
    row.units_used += units
    db.commit()
    db.refresh(row)
    return row


def remaining_quota_today(db: Session, *, budget: int) -> int:
    row = get_or_create_today_usage(db)
    return max(0, budget - row.units_used)
