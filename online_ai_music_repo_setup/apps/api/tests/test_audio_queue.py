import json
import uuid

from app.services.audio_queue import build_job_message


def test_build_job_message() -> None:
    job_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

    message = json.loads(build_job_message(job_id))

    assert message == {
        "job_id": str(job_id),
        "type": "generate_sine_wave",
        "version": 1,
    }
