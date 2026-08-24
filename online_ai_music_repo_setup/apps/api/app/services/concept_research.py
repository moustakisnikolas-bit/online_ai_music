import re
from collections import Counter

from sqlalchemy.orm import Session

from app.models.concept_research import ConceptResearch
from app.repositories.concept_research import upsert_concept_research
from app.repositories.youtube import get_youtube_credential
from app.repositories.youtube_quota import record_quota_usage
from app.services.youtube_publisher import credentials_from_stored, search_top_videos

# One representative real search query per concept, chosen to match how
# real, high-performing videos in this niche are actually titled/found
# (see the manual research that motivated this module) -- not just each
# concept's internal purpose_id/label, which isn't necessarily what
# people search for.
CONCEPT_RESEARCH_QUERIES = {
    "focus": "focus music frequency",
    "relaxation": "relaxation music",
    "mind_clearness": "meditation music frequency",
    # A bare "sleep music" query got swamped by billion-view kids'
    # nursery-rhyme content (real finding from a live run) -- "ambient"
    # narrows results back to the actual wellness/sleep-audio niche.
    "sleep": "deep sleep music ambient",
    "healing": "432hz healing music",
    "study": "study music white noise",
    "chakra": "chakra healing frequency music",
    # "deep_*" concepts get their own real query, not a reuse of the
    # base concept's -- "deep focus music" surfaces different real
    # top-viewed content than "focus music frequency" (longer runtimes,
    # different framing), which is the whole point of researching them
    # separately rather than assuming "deep" = same content relabeled.
    "deep_focus": "deep focus music long",
    "deep_relaxation": "deep relaxation music long",
    "deep_mind_clearness": "deep meditation music long",
    "deep_sleep": "deep sleep music 8 hours",
    "deep_healing": "deep healing frequency music long",
    "deep_study": "deep study music long",
    "deep_chakra": "deep chakra healing meditation long",
    # The single real query that surfaced the #1 video by view count
    # across this entire research effort (see concepts.py's
    # "triple_benefit" for the full analysis).
    "triple_benefit": "white noise black screen 10 hours",
}

# "Ultra" analysis: a deeper sample per query than the original 10 --
# search.list's quota cost is ~fixed per call regardless of maxResults
# (up to the API's own cap of 50), so this is a real increase in signal
# for negligible extra quota cost.
_ULTRA_MAX_RESULTS = 25

_DURATION_BUCKETS: tuple[tuple[str, int, float], ...] = (
    ("<15min", 0, 900),
    ("15-60min", 900, 3600),
    ("1-3hr", 3600, 10800),
    ("3-6hr", 10800, 21600),
    ("6-10hr", 21600, 36000),
    ("10hr+", 36000, float("inf")),
)

_ISO8601_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _parse_iso8601_duration_seconds(duration: str | None) -> int | None:
    if not duration:
        return None

    match = _ISO8601_DURATION_RE.match(duration)
    if not match:
        return None

    hours, minutes, seconds = (int(group) if group else 0 for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _duration_bucket(seconds: int) -> str:
    for label, lower, upper in _DURATION_BUCKETS:
        if lower <= seconds < upper:
            return label
    return _DURATION_BUCKETS[-1][0]

_NOISE_TERMS = [
    "white noise", "brown noise", "pink noise", "rain", "ocean", "fan sound", "nature",
]
_THEME_TERMS = [
    "healing", "focus", "sleep", "meditation", "relax", "anxiety", "chakra", "energy",
    "positive", "cleanse", "study", "stress", "binaural",
]
# search.list ~100 units + videos.list a few more -- recorded against
# the same quota ledger the upload pacer reads, so research never causes
# the pacer to over-schedule uploads.
_RESEARCH_QUOTA_COST_UNITS = 103


def _extract_hz_values(title: str) -> list[str]:
    return re.findall(r"(\d{2,4})\s?hz", title.lower())


def _extract_matching_terms(title: str, terms: list[str]) -> list[str]:
    title_lower = title.lower()
    return [term for term in terms if term in title_lower]


def analyze_videos(videos: list[dict]) -> dict:
    """Pure aggregation over already-fetched video dicts -- no I/O, so
    this is directly unit-testable without mocking the YouTube API.
    """
    hz_counter: Counter = Counter()
    noise_counter: Counter = Counter()
    theme_counter: Counter = Counter()
    duration_counter: Counter = Counter()

    for video in videos:
        title = video["title"]
        for hz in _extract_hz_values(title):
            hz_counter[hz] += 1
        for noise in _extract_matching_terms(title, _NOISE_TERMS):
            noise_counter[noise] += 1
        for theme in _extract_matching_terms(title, _THEME_TERMS):
            theme_counter[theme] += 1

        seconds = _parse_iso8601_duration_seconds(video.get("duration"))
        if seconds is not None:
            duration_counter[_duration_bucket(seconds)] += 1

    top_videos = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)[:5]

    return {
        "top_hz_values": [list(pair) for pair in hz_counter.most_common(10)],
        "top_noise_types": [list(pair) for pair in noise_counter.most_common(10)],
        "top_themes": [list(pair) for pair in theme_counter.most_common(10)],
        "top_duration_buckets": [list(pair) for pair in duration_counter.most_common(10)],
        "top_videos": [
            {
                "title": video["title"],
                "channel_title": video.get("channel_title"),
                "view_count": video.get("view_count", 0),
            }
            for video in top_videos
        ],
    }


def research_concept(db: Session, concept_id: str) -> ConceptResearch:
    if concept_id not in CONCEPT_RESEARCH_QUERIES:
        raise ValueError(f"Unknown concept: {concept_id!r}")

    credential = get_youtube_credential(db)
    if credential is None:
        raise ValueError(
            "No YouTube channel is connected -- research needs a real connected credential."
        )

    query = CONCEPT_RESEARCH_QUERIES[concept_id]
    credentials = credentials_from_stored(credential, db=db)
    videos = search_top_videos(credentials, query=query, max_results=_ULTRA_MAX_RESULTS)
    record_quota_usage(db, units=_RESEARCH_QUOTA_COST_UNITS)

    analysis = analyze_videos(videos)

    return upsert_concept_research(
        db,
        concept_id=concept_id,
        query=query,
        sample_size=len(videos),
        top_hz_values=analysis["top_hz_values"],
        top_noise_types=analysis["top_noise_types"],
        top_themes=analysis["top_themes"],
        top_duration_buckets=analysis["top_duration_buckets"],
        top_videos=analysis["top_videos"],
    )
