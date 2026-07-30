"""Tests for apps/worker/app/main.py.

Loaded via importlib rather than `from app.main import ...` because
apps/api/app and apps/worker/app are both top-level packages literally
named `app` -- whichever gets imported first in a pytest session wins that
name in sys.modules, silently shadowing the other (this is exactly the bug
that broke the worker's own script-style invocation earlier and had to be
fixed by using an absolute GENERATED_AUDIO_DIR). Loading by file path with
a distinct module name sidesteps the collision entirely rather than
depending on import order.
"""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest

_WORKER_MAIN_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"
_API_PATH = Path(__file__).resolve().parents[2] / "api"

if str(_API_PATH) not in sys.path:
    sys.path.insert(0, str(_API_PATH))

_spec = importlib.util.spec_from_file_location("worker_main", _WORKER_MAIN_PATH)
worker_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker_main)

from app.models.audio_job import AudioJob  # noqa: E402


@pytest.fixture
def db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.base import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AudioJob.__table__])

    monkeypatch.setattr(
        worker_main,
        "get_settings",
        lambda: type("S", (), {"audio_output_path": Path("/tmp/does-not-matter")})(),
    )

    with Session(engine) as session:
        yield session


def _queued_job(**overrides) -> AudioJob:
    defaults = dict(
        id=uuid.uuid4(),
        title="Test Tone",
        mode="sine",
        channels="mono",
        frequency_hz=432.0,
        modulation_depth=1.0,
        layers=[],
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0.1,
        fade_out_seconds=0.1,
        seamless_loop=False,
        loop_crossfade_seconds=0.25,
        status="queued",
    )
    defaults.update(overrides)
    return AudioJob(**defaults)


def test_process_job_missing_job_does_not_raise(db, capsys) -> None:
    worker_main.process_job(db, uuid.uuid4())

    assert "not found" in capsys.readouterr().out


def test_process_job_skips_wrong_status(db) -> None:
    job = _queued_job(status="completed")
    db.add(job)
    db.commit()

    worker_main.process_job(db, job.id)

    db.refresh(job)
    assert job.status == "completed"
    assert job.started_at is None


def test_process_job_completes_successfully(db, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        worker_main,
        "get_settings",
        lambda: type("S", (), {"audio_output_path": tmp_path})(),
    )

    job = _queued_job()
    db.add(job)
    db.commit()

    worker_main.process_job(db, job.id)

    db.refresh(job)
    assert job.status == "completed"
    assert job.output_file_path is not None
    assert Path(job.output_file_path).exists()
    assert job.started_at is not None
    assert job.completed_at is not None


def test_process_job_marks_failed_on_generation_error(db, monkeypatch) -> None:
    def _boom(**_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(worker_main, "generate_audio", _boom)

    job = _queued_job()
    db.add(job)
    db.commit()

    worker_main.process_job(db, job.id)

    db.refresh(job)
    assert job.status == "failed"
    assert "synthetic failure" in job.error_message


def test_process_job_accepts_retry_status(db, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        worker_main,
        "get_settings",
        lambda: type("S", (), {"audio_output_path": tmp_path})(),
    )

    job = _queued_job(status="retry")
    db.add(job)
    db.commit()

    worker_main.process_job(db, job.id)

    db.refresh(job)
    assert job.status == "completed"
