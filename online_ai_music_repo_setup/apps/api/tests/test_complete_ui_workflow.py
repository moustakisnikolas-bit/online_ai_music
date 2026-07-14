from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_complete_ui_contains_all_workflow_steps() -> None:
    response = client.get("/")

    assert response.status_code == 200

    expected_text = [
        "Run complete workflow",
        "Audio",
        "Metadata",
        "Artwork",
        "Video",
        "Export bundle",
        "Download export ZIP",
    ]

    for text in expected_text:
        assert text in response.text
