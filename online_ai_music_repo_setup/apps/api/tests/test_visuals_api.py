from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.api.routes import visuals
from app.main import app
from app.services.ai_artwork_generator import ArtworkGenerationResult

client = TestClient(app)


def test_generate_artwork_endpoint_defaults_to_procedural(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(visuals, "_AI_ARTWORK_DIR", tmp_path)

    response = client.post(
        "/api/v1/visuals/artwork/generate",
        json={"title": "Night Rain", "preset_name": "square-preview"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preset_name"] == "square-preview"
    assert Path(body["file_path"]).exists()


def test_generate_artwork_endpoint_rejects_unconfigured_ai_provider(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(visuals, "_AI_ARTWORK_DIR", tmp_path)

    response = client.post(
        "/api/v1/visuals/artwork/generate",
        json={
            "title": "Night Rain",
            "preset_name": "square-preview",
            "provider": "openrouter",
        },
    )

    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]


def test_generate_artwork_endpoint_routes_ai_provider_correctly(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(visuals, "_AI_ARTWORK_DIR", tmp_path)

    captured: dict = {}

    def _fake_generate_ai_artwork(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        kwargs["output_path"].write_bytes(b"fake-image-bytes")
        return ArtworkGenerationResult(path=kwargs["output_path"], cost_usd=None)

    monkeypatch.setattr(visuals, "generate_ai_artwork", _fake_generate_ai_artwork)

    response = client.post(
        "/api/v1/visuals/artwork/generate",
        json={
            "title": "Night Rain",
            "preset_name": "youtube-thumbnail",
            "provider": "replicate",
            "style_prompt": "rain over a quiet lake at dusk",
        },
    )

    assert response.status_code == 200
    assert captured["prompt"] == "rain over a quiet lake at dusk"
    assert captured["kwargs"]["provider"] == "replicate"
    assert captured["kwargs"]["width"] == 1280
    assert captured["kwargs"]["height"] == 720
    assert Path(response.json()["file_path"]).read_bytes() == b"fake-image-bytes"


def test_generate_artwork_endpoint_returns_clean_json_on_upstream_http_error(
    tmp_path: Path, monkeypatch
) -> None:
    # Regression test: a real Replicate 402 (Payment Required, e.g. no
    # billing set up) raised httpx.HTTPStatusError, which this route
    # didn't catch -- it crashed as a raw 500 with a plain-text/HTML
    # body, and the frontend's JSON parser choked on "Internal S..."
    # instead of showing a real error message.
    monkeypatch.setattr(visuals, "_AI_ARTWORK_DIR", tmp_path)

    def _fake_generate_ai_artwork(prompt, **kwargs):
        request = httpx.Request("POST", "https://api.replicate.com/v1/models/x/predictions")
        response = httpx.Response(402, request=request, text="Payment Required")
        raise httpx.HTTPStatusError("402 Payment Required", request=request, response=response)

    monkeypatch.setattr(visuals, "generate_ai_artwork", _fake_generate_ai_artwork)

    response = client.post(
        "/api/v1/visuals/artwork/generate",
        json={
            "title": "Night Rain",
            "preset_name": "square-preview",
            "provider": "replicate",
        },
    )

    assert response.status_code == 502
    assert "402" in response.json()["detail"]


def test_generate_artwork_endpoint_rejects_unknown_preset() -> None:
    response = client.post(
        "/api/v1/visuals/artwork/generate",
        json={"title": "Night Rain", "preset_name": "not-a-real-preset"},
    )

    assert response.status_code == 400


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
