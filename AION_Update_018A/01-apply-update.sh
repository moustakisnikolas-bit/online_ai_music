#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/services/video_renderer.py")
content = path.read_text(encoding="utf-8")

old = """    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required for MP4 rendering.")

    audio_path = _safe_file(
        audio_dir,
        audio_filename,
        {".wav", ".flac", ".mp3"},
    )
    artwork_path = _safe_file(
        artwork_dir,
        artwork_filename,
        {".png", ".jpg", ".jpeg"},
    )

    if Path(output_filename).name != output_filename:
        raise ValueError("Invalid output filename")

    if not output_filename.lower().endswith(".mp4"):
        raise ValueError("Output filename must end with .mp4")
"""

new = """    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required for MP4 rendering.")

    if Path(output_filename).name != output_filename:
        raise ValueError("Invalid output filename")

    if not output_filename.lower().endswith(".mp4"):
        raise ValueError("Output filename must end with .mp4")

    audio_path = _safe_file(
        audio_dir,
        audio_filename,
        {".wav", ".flac", ".mp3"},
    )
    artwork_path = _safe_file(
        artwork_dir,
        artwork_filename,
        {".png", ".jpg", ".jpeg"},
    )
"""

if old not in content:
    raise SystemExit("Expected renderer validation block was not found.")

path.write_text(content.replace(old, new), encoding="utf-8")
PY

cat > apps/api/tests/test_video_renderer_validation_order.py <<'EOF'
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.video_renderer import render_static_video


def test_invalid_output_filename_is_checked_before_inputs(
    tmp_path: Path,
) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="Invalid output filename"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="missing.wav",
                artwork_filename="missing.png",
                output_filename="../unsafe.mp4",
            )
EOF

echo "AION Update 018A applied successfully."
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
