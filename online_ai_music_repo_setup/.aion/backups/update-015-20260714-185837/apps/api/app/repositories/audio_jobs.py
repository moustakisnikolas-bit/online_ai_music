import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_job import AudioJob
from app.schemas.audio_job import AudioJobCreate


def create_audio_job(db: Session, payload: AudioJobCreate) -> AudioJob:
    job = AudioJob(
        project_id=payload.project_id,
        title=payload.title,
        mode=payload.mode.value,
        channels=payload.channels.value,
        frequency_hz=payload.frequency_hz,
        left_frequency_hz=payload.left_frequency_hz,
        right_frequency_hz=payload.right_frequency_hz,
        pulse_frequency_hz=payload.pulse_frequency_hz,
        modulation_depth=payload.modulation_depth,
        layers=[layer.model_dump() for layer in payload.layers],
        preset_name=payload.preset_name,
        duration_seconds=payload.duration_seconds,
        sample_rate=payload.sample_rate,
        amplitude=payload.amplitude,
        fade_in_seconds=payload.fade_in_seconds,
        fade_out_seconds=payload.fade_out_seconds,
        seamless_loop=payload.seamless_loop,
        loop_crossfade_seconds=payload.loop_crossfade_seconds,
        seed=payload.seed,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_audio_job(db: Session, job_id: uuid.UUID) -> AudioJob | None:
    return db.get(AudioJob, job_id)


def list_audio_jobs(db: Session, limit: int = 50) -> list[AudioJob]:
    statement = (
        select(AudioJob)
        .order_by(AudioJob.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))
