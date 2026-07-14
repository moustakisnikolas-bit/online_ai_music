import json
import uuid

from redis import Redis

from app.core.config import get_settings

QUEUE_NAME = "aion:audio:jobs"


def build_job_message(job_id: uuid.UUID) -> str:
    return json.dumps(
        {
            "job_id": str(job_id),
            "type": "generate_sine_wave",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def enqueue_audio_job(job_id: uuid.UUID) -> None:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    client.lpush(QUEUE_NAME, build_job_message(job_id))
