import pytest
from pydantic import ValidationError

from app.schemas.track_rating import TrackRatingCreate


def test_track_rating_create_defaults_to_all_optional() -> None:
    rating = TrackRatingCreate()

    assert rating.stress_before is None
    assert rating.completed_listen is None
    assert rating.preferred_instruments == []
    assert rating.uncomfortable_sounds == []


def test_track_rating_create_accepts_valid_values() -> None:
    rating = TrackRatingCreate(
        stress_before=8,
        stress_after=3,
        mood_before=4,
        mood_after=8,
        sleep_onset_minutes=15,
        completed_listen=True,
        preferred_instruments=["felt_piano", "rain"],
        uncomfortable_sounds=["birds"],
        notes="Fell asleep faster than usual.",
    )

    assert rating.stress_before == 8
    assert rating.preferred_instruments == ["felt_piano", "rain"]


@pytest.mark.parametrize("field", ["stress_before", "stress_after", "mood_before", "mood_after"])
def test_track_rating_create_rejects_out_of_range_scale_values(field: str) -> None:
    with pytest.raises(ValidationError):
        TrackRatingCreate(**{field: 11})

    with pytest.raises(ValidationError):
        TrackRatingCreate(**{field: 0})


def test_track_rating_create_rejects_negative_sleep_onset() -> None:
    with pytest.raises(ValidationError):
        TrackRatingCreate(sleep_onset_minutes=-5)


def test_track_rating_create_rejects_negative_skip_position() -> None:
    with pytest.raises(ValidationError):
        TrackRatingCreate(skipped_at_seconds=-1)
