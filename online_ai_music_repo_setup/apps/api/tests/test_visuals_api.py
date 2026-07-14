from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_visual_presets_endpoint() -> None:
    response = client.get("/api/v1/visuals/presets")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["name"] == "spotify-cover" for item in payload)


def test_generate_video_manifest_endpoint() -> None:
    response = client.post(
        "/api/v1/visuals/video/manifest",
        json={
            "title": "Night Rain",
            "audio_filename": "night-rain.wav",
            "artwork_filename": "night-rain.png",
            "duration_seconds": 600,
        },
    )

    assert response.status_code == 200
    assert response.json()["manifest_filename"].endswith(
        ".video-manifest.json"
    )
