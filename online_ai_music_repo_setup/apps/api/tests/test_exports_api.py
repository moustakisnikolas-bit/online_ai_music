from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import exports
from app.main import app

client = TestClient(app)


def test_list_rendered_videos_returns_empty_when_no_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(exports, "VIDEO_DIR", tmp_path / "does-not-exist")

    response = client.get("/api/v1/exports/videos")

    assert response.status_code == 200
    assert response.json() == []


def test_list_rendered_videos_lists_mp4_files_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(exports, "VIDEO_DIR", tmp_path)

    (tmp_path / "night-rain.mp4").write_bytes(b"fake mp4 bytes")
    (tmp_path / "not-a-video.txt").write_bytes(b"ignore me")
    (tmp_path / "manifest.video-manifest.json").write_text("{}")

    response = client.get("/api/v1/exports/videos")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "night-rain.mp4"
    assert body[0]["size_bytes"] == len(b"fake mp4 bytes")
    assert "modified_at" in body[0]
