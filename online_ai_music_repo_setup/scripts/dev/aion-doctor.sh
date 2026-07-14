#!/usr/bin/env bash
set -e
echo "=== AION Doctor ==="
echo "Python: $(python3 --version 2>/dev/null || echo missing)"
echo "Git: $(git --version 2>/dev/null || echo missing)"
if command -v ffmpeg >/dev/null; then
  echo "FFmpeg: OK"
else
  echo "FFmpeg: MISSING"
fi
if command -v docker >/dev/null; then
  echo "Docker: OK"
else
  echo "Docker: MISSING"
fi
echo "Repo: $(pwd)"
echo "==================="
