"""Prints the number of tracks not yet uploaded to YouTube (real count
from the local database, not an estimate). Used by
youtube_reconnect_reminder.ps1 to decide whether the reminder still needs
to bother the user -- once this hits 0, the backlog is fully uploaded and
the reminder should stay silent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.albums import list_album_batches, list_album_tracks  # noqa: E402

# Same definition daily_upload_report.py uses for "still queued."
_NOT_YET_UPLOADED_STATUSES = {"pending", "harmony_passed", "audio_rendered", "video_rendered"}


def main() -> None:
    db = SessionLocal()
    try:
        count = 0
        for batch in list_album_batches(db, limit=500):
            for track in list_album_tracks(db, batch.id):
                if track.status in _NOT_YET_UPLOADED_STATUSES:
                    count += 1
        print(count)
    finally:
        db.close()


if __name__ == "__main__":
    main()
