import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.audio_job import AudioJob
from app.repositories.youtube import create_youtube_publication

client = TestClient(app)


def _create_job(**overrides) -> uuid.UUID:
    db = SessionLocal()
    try:
        job = AudioJob(
            title=overrides.get("title", "Delete Me"),
            mode="sine",
            duration_seconds=1,
            status=overrides.get("status", "completed"),
            review_status=overrides.get("review_status", "pending"),
            output_file_path=overrides.get("output_file_path"),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id
    finally:
        db.close()


def _job_exists(job_id: uuid.UUID) -> bool:
    db = SessionLocal()
    try:
        return db.get(AudioJob, job_id) is not None
    finally:
        db.close()


def test_delete_audio_job_removes_it() -> None:
    job_id = _create_job()

    response = client.delete(f"/api/v1/audio/jobs/{job_id}")

    assert response.status_code == 200
    assert not _job_exists(job_id)

    follow_up = client.get(f"/api/v1/audio/jobs/{job_id}")
    assert follow_up.status_code == 404


def test_delete_unknown_job_returns_404() -> None:
    response = client.delete(f"/api/v1/audio/jobs/{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_audio_job_also_removes_output_file(tmp_path: Path) -> None:
    audio_file = tmp_path / "track.wav"
    audio_file.write_bytes(b"fake wav bytes")

    job_id = _create_job(output_file_path=str(audio_file))

    response = client.delete(f"/api/v1/audio/jobs/{job_id}")

    assert response.status_code == 200
    assert not audio_file.exists()


def test_delete_audio_job_cascades_youtube_publication() -> None:
    job_id = _create_job()

    db = SessionLocal()
    try:
        create_youtube_publication(
            db, audio_job_id=job_id, video_filename="clip.mp4", title="Night Rain"
        )
    finally:
        db.close()

    # Would raise an IntegrityError at the DB level without the cascade
    # delete inside delete_audio_job -- confirms the FK cleanup works.
    response = client.delete(f"/api/v1/audio/jobs/{job_id}")

    assert response.status_code == 200
    assert not _job_exists(job_id)


def test_bulk_delete_multiple_jobs_and_reports_not_found() -> None:
    job_id_1 = _create_job(title="Bulk 1")
    job_id_2 = _create_job(title="Bulk 2")
    missing_id = uuid.uuid4()

    response = client.post(
        "/api/v1/audio/jobs/bulk-delete",
        json={"job_ids": [str(job_id_1), str(job_id_2), str(missing_id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["deleted_ids"]) == {str(job_id_1), str(job_id_2)}
    assert body["not_found_ids"] == [str(missing_id)]
    assert not _job_exists(job_id_1)
    assert not _job_exists(job_id_2)


def test_bulk_delete_rejects_empty_list() -> None:
    response = client.post("/api/v1/audio/jobs/bulk-delete", json={"job_ids": []})

    assert response.status_code == 422
