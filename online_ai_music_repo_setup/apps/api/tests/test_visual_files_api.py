from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def test_visual_file_endpoint() -> None:
    output_dir = Path("data/generated/artwork")
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / "ui-test-image.png"
    Image.new("RGB", (10, 10)).save(path)

    try:
        response = client.get(
            "/api/v1/visuals/files/ui-test-image.png"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    finally:
        path.unlink(missing_ok=True)
