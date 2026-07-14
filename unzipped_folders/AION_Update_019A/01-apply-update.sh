#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

cat > apps/api/tests/test_web_ui.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_web_home_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AION Ambient Media Factory" in response.text
    assert "Run complete workflow" in response.text


def test_web_app_alias_is_available() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
EOF

echo "AION Update 019A applied successfully."
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
