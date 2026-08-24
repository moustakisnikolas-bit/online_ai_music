import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.concept_research import ConceptResearch
from app.models.youtube_publishing import YouTubeCredential, YouTubeQuotaUsage
from app.repositories.concept_research import get_concept_research
from app.services import concept_research
from app.services.concept_research import (
    CONCEPT_RESEARCH_QUERIES,
    _duration_bucket,
    _parse_iso8601_duration_seconds,
    analyze_videos,
    research_concept,
)


def test_analyze_videos_extracts_hz_values_ranked_by_frequency() -> None:
    videos = [
        {"title": "528Hz Deep Healing Music", "channel_title": "A", "view_count": 100},
        {"title": "528Hz Positive Transformation", "channel_title": "B", "view_count": 50},
        {"title": "432Hz Relaxation Music", "channel_title": "C", "view_count": 10},
    ]

    result = analyze_videos(videos)

    assert result["top_hz_values"][0] == ["528", 2]
    assert result["top_hz_values"][1] == ["432", 1]


def test_analyze_videos_extracts_noise_types() -> None:
    videos = [
        {"title": "White Noise for Sleep", "channel_title": "A", "view_count": 1},
        {"title": "Rain Sounds for Focus", "channel_title": "B", "view_count": 1},
        {"title": "White Noise Black Screen", "channel_title": "C", "view_count": 1},
    ]

    result = analyze_videos(videos)
    noise_dict = dict(result["top_noise_types"])

    assert noise_dict["white noise"] == 2
    assert noise_dict["rain"] == 1
    assert "brown noise" not in noise_dict


def test_analyze_videos_extracts_theme_keywords() -> None:
    videos = [
        {"title": "Study Focus Music for Concentration", "channel_title": "A", "view_count": 1},
        {"title": "Sleep Music for Deep Relax", "channel_title": "B", "view_count": 1},
    ]

    result = analyze_videos(videos)
    theme_dict = dict(result["top_themes"])

    assert theme_dict["study"] == 1
    assert theme_dict["focus"] == 1
    assert theme_dict["sleep"] == 1
    assert theme_dict["relax"] == 1


def test_analyze_videos_ranks_top_videos_by_real_view_count() -> None:
    videos = [
        {"title": "Low views", "channel_title": "A", "view_count": 10},
        {"title": "High views", "channel_title": "B", "view_count": 1_000_000},
        {"title": "Mid views", "channel_title": "C", "view_count": 500},
    ]

    result = analyze_videos(videos)

    assert result["top_videos"][0]["title"] == "High views"
    assert result["top_videos"][0]["view_count"] == 1_000_000
    assert result["top_videos"][-1]["title"] == "Low views"


def test_analyze_videos_handles_empty_list() -> None:
    result = analyze_videos([])

    assert result["top_hz_values"] == []
    assert result["top_noise_types"] == []
    assert result["top_themes"] == []
    assert result["top_duration_buckets"] == []
    assert result["top_videos"] == []


@pytest.mark.parametrize(
    ("duration", "expected_seconds"),
    [
        ("PT14M55S", 895),
        ("PT3H45M12S", 13512),
        ("PT10H", 36000),
        ("PT45S", 45),
        (None, None),
        ("", None),
        ("not-a-duration", None),
    ],
)
def test_parse_iso8601_duration_seconds(duration, expected_seconds) -> None:
    assert _parse_iso8601_duration_seconds(duration) == expected_seconds


@pytest.mark.parametrize(
    ("seconds", "expected_bucket"),
    [
        (300, "<15min"),
        (899, "<15min"),
        (900, "15-60min"),
        (3599, "15-60min"),
        (3600, "1-3hr"),
        (10799, "1-3hr"),
        (10800, "3-6hr"),
        (21599, "3-6hr"),
        (21600, "6-10hr"),
        (35999, "6-10hr"),
        (36000, "10hr+"),
        (100000, "10hr+"),
    ],
)
def test_duration_bucket(seconds, expected_bucket) -> None:
    assert _duration_bucket(seconds) == expected_bucket


def test_analyze_videos_buckets_real_video_durations() -> None:
    videos = [
        {"title": "A", "channel_title": "x", "view_count": 1, "duration": "PT3H30M"},
        {"title": "B", "channel_title": "x", "view_count": 1, "duration": "PT4H"},
        {"title": "C", "channel_title": "x", "view_count": 1, "duration": "PT10M"},
        {"title": "D", "channel_title": "x", "view_count": 1, "duration": None},
    ]

    result = analyze_videos(videos)
    buckets = dict(result["top_duration_buckets"])

    assert buckets["3-6hr"] == 2
    assert buckets["<15min"] == 1
    assert sum(buckets.values()) == 3  # the missing-duration video is skipped, not miscounted


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # YouTubeCredential deliberately excluded -- same established
    # workaround as the album pipeline tests: its "scopes" column uses
    # postgresql.ARRAY, which SQLite can't compile.
    Base.metadata.create_all(
        engine, tables=[ConceptResearch.__table__, YouTubeQuotaUsage.__table__]
    )

    with Session(engine) as session:
        yield session


def test_research_concept_rejects_unknown_concept(db) -> None:
    with pytest.raises(ValueError, match="Unknown concept"):
        research_concept(db, "not_a_real_concept")


def test_research_concept_requires_a_connected_youtube_channel(monkeypatch, db) -> None:
    monkeypatch.setattr(concept_research, "get_youtube_credential", lambda db: None)

    with pytest.raises(ValueError, match="No YouTube channel"):
        research_concept(db, "focus")


def test_research_concept_persists_real_search_results(monkeypatch, db) -> None:
    fake_credential = YouTubeCredential(
        channel_id="UC-fake", channel_title="Fake Channel",
        access_token="enc-access", refresh_token="enc-refresh", token_expiry=None,
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    monkeypatch.setattr(concept_research, "get_youtube_credential", lambda db: fake_credential)
    monkeypatch.setattr(concept_research, "credentials_from_stored", lambda credential, *, db: object())

    fake_videos = [
        {"video_id": "v1", "title": "528Hz Focus Music - White Noise", "channel_title": "X", "view_count": 999},
    ]
    captured_queries = []

    def _fake_search_top_videos(credentials, *, query, max_results):
        captured_queries.append(query)
        return fake_videos

    monkeypatch.setattr(concept_research, "search_top_videos", _fake_search_top_videos)

    record = research_concept(db, "focus")

    assert captured_queries == [CONCEPT_RESEARCH_QUERIES["focus"]]
    assert record.concept_id == "focus"
    assert record.sample_size == 1
    assert record.top_hz_values == [["528", 1]]
    assert dict(record.top_noise_types)["white noise"] == 1

    stored = get_concept_research(db, "focus")
    assert stored is not None
    assert stored.id == record.id


def test_research_concept_upserts_not_duplicates(monkeypatch, db) -> None:
    fake_credential = YouTubeCredential(
        channel_id="UC-fake", channel_title="Fake Channel",
        access_token="enc-access", refresh_token="enc-refresh", token_expiry=None,
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    monkeypatch.setattr(concept_research, "get_youtube_credential", lambda db: fake_credential)
    monkeypatch.setattr(concept_research, "credentials_from_stored", lambda credential, *, db: object())
    monkeypatch.setattr(
        concept_research, "search_top_videos",
        lambda credentials, *, query, max_results: [
            {"video_id": "v1", "title": "432Hz Relaxation", "channel_title": "X", "view_count": 1}
        ],
    )

    first = research_concept(db, "relaxation")
    second = research_concept(db, "relaxation")

    assert first.id == second.id
    from sqlalchemy import select
    all_rows = db.scalars(select(ConceptResearch)).all()
    assert len(all_rows) == 1
