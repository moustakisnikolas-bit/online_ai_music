import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redis import Redis
from sqlalchemy.orm import Session

API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.audio.types import AudioMode, ChannelMode  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.audio_job import AudioJob  # noqa: E402
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest  # noqa: E402
from app.services.audio_generator import generate_audio  # noqa: E402
from app.services.audio_queue import QUEUE_NAME  # noqa: E402


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def process_job(db: Session, job_id: uuid.UUID) -> None:
    settings = get_settings()
    job = db.get(AudioJob, job_id)

    if job is None:
        print(f"Audio job not found: {job_id}", flush=True)
        return

    if job.status not in {"queued", "retry"}:
        print(f"Skipping job {job_id} with status {job.status}", flush=True)
        return

    job.status = "processing"
    job.started_at = utc_now()
    job.error_message = None
    db.commit()

    try:
        request = AudioGenerationRequest(
            title=job.title,
            mode=AudioMode(job.mode),
            channels=ChannelMode(job.channels),
            frequency_hz=job.frequency_hz,
            left_frequency_hz=job.left_frequency_hz,
            right_frequency_hz=job.right_frequency_hz,
            pulse_frequency_hz=job.pulse_frequency_hz,
            modulation_depth=job.modulation_depth,
            layers=[
                ToneLayerRequest(**layer)
                for layer in (job.layers or [])
            ],
            preset_name=job.preset_name,
            duration_seconds=job.duration_seconds,
            sample_rate=job.sample_rate,
            amplitude=job.amplitude,
            fade_in_seconds=job.fade_in_seconds,
            fade_out_seconds=job.fade_out_seconds,
            seamless_loop=job.seamless_loop,
            loop_crossfade_seconds=job.loop_crossfade_seconds,
            seed=job.seed,
        )

        result = generate_audio(
            request=request,
            output_dir=settings.audio_output_path,
        )

        job.status = "completed"
        job.output_file_path = result.file_path
        job.completed_at = utc_now()
        db.commit()
        print(f"Completed audio job: {job_id}", flush=True)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = utc_now()
        db.commit()
        print(f"Failed audio job {job_id}: {exc}", flush=True)


def run_worker() -> None:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)

    print(
        f"AION audio worker started. Queue: {QUEUE_NAME}. Redis: {settings.redis_url}",
        flush=True,
    )

    while True:
        item = client.brpop(QUEUE_NAME, timeout=10)

        if item is None:
            continue

        _, raw_message = item

        try:
            message = json.loads(raw_message)
            job_id = uuid.UUID(message["job_id"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"Invalid queue message: {raw_message}. Error: {exc}", flush=True)
            continue

        db = SessionLocal()
        try:
            process_job(db, job_id)
        finally:
            db.close()


if __name__ == "__main__":
    run_worker()
