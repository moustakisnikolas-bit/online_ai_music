from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_web_home_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AION Ambient Audio Factory" in response.text
    assert "Generate audio" in response.text


def test_web_app_alias_is_available() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
