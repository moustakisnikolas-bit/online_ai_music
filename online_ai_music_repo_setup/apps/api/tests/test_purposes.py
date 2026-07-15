import pytest
from fastapi.testclient import TestClient

from app.audio.purposes import PURPOSES, get_purpose, list_purposes
from app.main import app

client = TestClient(app)


def test_list_purposes_returns_all_six_categories() -> None:
    profiles = list_purposes()
    assert len(profiles) == 6
    assert {profile["id"] for profile in profiles} == {
        "sleep",
        "stress_relief",
        "meditation",
        "calm_focus",
        "anxiety_calming",
        "pain_comfort",
    }


def test_get_purpose_found_and_not_found() -> None:
    profile = get_purpose("sleep")
    assert profile.label == "Deep Sleep"
    assert profile.true_peak_dbtp == -2.0

    with pytest.raises(ValueError, match="Unknown purpose"):
        get_purpose("does-not-exist")


def test_every_purpose_target_lufs_is_within_a_plausible_range() -> None:
    for profile in PURPOSES.values():
        assert -25 <= profile.target_lufs <= -10
        assert 0 < profile.energy_start <= 1.0
        assert 0 < profile.energy_middle <= 1.0
        assert 0 < profile.energy_end <= 1.0


def test_list_purposes_endpoint() -> None:
    response = client.get("/api/v1/audio/purposes")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 6


def test_get_purpose_endpoint() -> None:
    response = client.get("/api/v1/audio/purposes/meditation")
    assert response.status_code == 200
    assert response.json()["label"] == "Meditation"


def test_get_purpose_endpoint_404() -> None:
    response = client.get("/api/v1/audio/purposes/nonexistent")
    assert response.status_code == 404
