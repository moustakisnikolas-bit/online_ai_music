"""Daily album-pipeline report: how many tracks are still waiting to be
uploaded, and which ones uploaded today (real titles + YouTube URLs).

Run once a day via Windows Task Scheduler (see docs/daily-upload-report.md
for the scheduled-task setup). Writes to
scripts/ops/daily_reports/report-YYYY-MM-DD.txt and refreshes latest.txt
with the same content, so there's always one stable path to check.

Reads the local Postgres database directly through the app's own models --
no server needs to be running for this to work, only the database
container.
"""

import sys
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.db.session import SessionLocal  # noqa: E402
from app.models.youtube_publishing import YouTubePublication  # noqa: E402
from app.repositories.albums import list_album_batches, list_album_tracks  # noqa: E402
from app.repositories.youtube_quota import today_pacific  # noqa: E402

# Same timezone youtube_quota.py paces uploads against -- a track's
# uploaded_at (stored UTC) needs to land on the *Pacific* calendar day to
# match "today" the way the rest of this system defines it.
_PACIFIC = ZoneInfo("America/Los_Angeles")

REPORT_DIR = Path(__file__).resolve().parent / "daily_reports"

# "uploaded" is real progress (the video is live on YouTube) but not yet
# in its playlist -- distinct from the pipeline's own TERMINAL_TRACK_STATUSES,
# which only covers "playlist_added"/"failed". This report cares about a
# third real state: not-yet-uploaded-at-all, the actual upload queue.
_NOT_YET_UPLOADED_STATUSES = {"pending", "harmony_passed", "audio_rendered", "video_rendered"}


def build_report() -> str:
    db = SessionLocal()
    try:
        today = today_pacific()
        batches = list_album_batches(db, limit=500)

        queued = []
        uploaded_awaiting_playlist = []
        playlist_added = []
        failed = []
        uploaded_today = []

        for batch in batches:
            for track in list_album_tracks(db, batch.id):
                if track.status in _NOT_YET_UPLOADED_STATUSES:
                    queued.append((batch, track))
                elif track.status == "uploaded":
                    uploaded_awaiting_playlist.append((batch, track))
                elif track.status == "playlist_added":
                    playlist_added.append((batch, track))
                elif track.status == "failed":
                    failed.append((batch, track))

                if track.uploaded_at is not None:
                    # uploaded_at comes back naive from this driver despite
                    # the timezone(True) column -- it's UTC by convention
                    # (always written via datetime.now(timezone.utc)), so
                    # tag it explicitly before converting rather than
                    # letting astimezone() assume local system time.
                    uploaded_at_utc = track.uploaded_at.replace(tzinfo=timezone.utc)
                    uploaded_date = uploaded_at_utc.astimezone(_PACIFIC).date()
                    if uploaded_date == today:
                        publication = (
                            db.get(YouTubePublication, track.youtube_publication_id)
                            if track.youtube_publication_id
                            else None
                        )
                        uploaded_today.append((batch, track, publication))

        lines = []
        lines.append(f"AION daily upload report -- {today.isoformat()} (Pacific)")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Still queued for upload (not yet on YouTube): {len(queued)}")
        lines.append(f"Uploaded, waiting to join their playlist:      {len(uploaded_awaiting_playlist)}")
        lines.append(f"Fully done (uploaded + in playlist):           {len(playlist_added)}")
        if failed:
            lines.append(f"Failed (needs attention):                      {len(failed)}")
        lines.append("")

        lines.append(f"Uploaded today ({len(uploaded_today)}):")
        if not uploaded_today:
            lines.append("  (none yet today)")
        else:
            for batch, track, publication in sorted(uploaded_today, key=lambda item: item[1].uploaded_at):
                url = publication.youtube_url if publication else "(no URL on record)"
                lines.append(f"  - [{batch.concept_id}] {track.title}")
                lines.append(f"      {url}")
        lines.append("")

        lines.append("Still queued, by concept:")
        by_concept: dict[str, int] = {}
        for batch, _track in queued:
            by_concept[batch.concept_id] = by_concept.get(batch.concept_id, 0) + 1
        if not by_concept:
            lines.append("  (nothing queued)")
        else:
            for concept_id, count in sorted(by_concept.items(), key=lambda pair: -pair[1]):
                lines.append(f"  - {concept_id}: {count}")

        if failed:
            lines.append("")
            lines.append("Failed tracks (needs attention):")
            for batch, track in failed:
                lines.append(f"  - [{batch.concept_id}] {track.title}: {track.error_message or '(no error message)'}")

        return "\n".join(lines) + "\n"
    finally:
        db.close()


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()

    today = today_pacific()
    dated_path = REPORT_DIR / f"report-{today.isoformat()}.txt"
    dated_path.write_text(report, encoding="utf-8")
    (REPORT_DIR / "latest.txt").write_text(report, encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
