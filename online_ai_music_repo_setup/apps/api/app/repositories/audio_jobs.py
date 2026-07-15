import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_job import AudioJob
from app.schemas.audio import AudioGenerationRequest, AudioGenerationResponse
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


def create_completed_audio_job(
    db: Session,
    *,
    request: AudioGenerationRequest,
    response: AudioGenerationResponse,
) -> AudioJob:
    # Persists a job that has already been generated synchronously (the
    # web UI's direct generate flow), rather than one submitted to the
    # Redis-backed queue for a worker to pick up. This is what makes a
    # synchronously generated track show up in the review/publish
    # pipeline, which otherwise only ever sees queue-submitted jobs.
    # ambient_layers (mixed_ambient) has no dedicated column yet, so those
    # layers aren't reconstructable from the row -- only the audio file
    # and the descriptive fields the catalog view needs are persisted.
    now = datetime.now(timezone.utc)
    job = AudioJob(
        title=request.title,
        mode=request.mode.value,
        channels=request.channels.value,
        frequency_hz=request.frequency_hz,
        left_frequency_hz=request.left_frequency_hz,
        right_frequency_hz=request.right_frequency_hz,
        pulse_frequency_hz=request.pulse_frequency_hz,
        modulation_depth=request.modulation_depth,
        layers=[layer.model_dump() for layer in request.layers],
        preset_name=request.preset_name,
        duration_seconds=request.duration_seconds,
        sample_rate=request.sample_rate,
        amplitude=request.amplitude,
        fade_in_seconds=request.fade_in_seconds,
        fade_out_seconds=request.fade_out_seconds,
        seamless_loop=request.seamless_loop,
        loop_crossfade_seconds=request.loop_crossfade_seconds,
        seed=request.seed,
        status="completed",
        review_status="pending",
        output_file_path=response.file_path,
        started_at=now,
        completed_at=now,
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
