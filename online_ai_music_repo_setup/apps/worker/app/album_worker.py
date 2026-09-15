import sys
import time
from pathlib import Path

API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.db.session import SessionLocal  # noqa: E402
from app.services.album_pipeline import run_album_worker_tick  # noqa: E402
from app.services.shorts_pipeline import run_shorts_worker_tick  # noqa: E402

POLL_INTERVAL_SECONDS = 30


def run_album_worker() -> None:
    # A plain poll loop, not folded into apps/worker/app/main.py's Redis
    # BRPOP consumer -- that loop blocks on real audio-job processing and
    # isn't a safe place to interleave hours-spanning upload pacing. No
    # new scheduler dependency (APScheduler/Celery-beat) either -- this is
    # the same simplicity level as the existing worker.
    print(
        f"AION album pipeline worker started. Polling every {POLL_INTERVAL_SECONDS}s.",
        flush=True,
    )

    while True:
        db = SessionLocal()
        try:
            run_album_worker_tick(db)
            # A complete no-op while shorts_enabled is False (see
            # shorts_pipeline.py) -- always safe to call regardless of
            # the flag's value.
            run_shorts_worker_tick(db)
        except Exception as exc:
            print(f"Album worker tick failed: {exc}", flush=True)
        finally:
            db.close()

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_album_worker()
