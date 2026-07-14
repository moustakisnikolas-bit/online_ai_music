#!/usr/bin/env bash
set -Eeuo pipefail
TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"
cd "$TARGET"

mkdir -p scripts/dev docs/99-release

cat > scripts/dev/aion-doctor.sh <<'EOF'
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
EOF
chmod +x scripts/dev/aion-doctor.sh

cat > docs/99-release/FINAL_CHECKLIST.md <<'EOF'
# Final Checklist

- [ ] make test passes
- [ ] API starts
- [ ] UI loads
- [ ] Audio generation works
- [ ] Artwork generation works
- [ ] Metadata generation works
- [ ] Export ZIP works
- [ ] FFmpeg installed (optional for MP4)
- [ ] Docker installed (optional)
EOF

cat > docs/99-release/IMPLEMENTATION_PROMPT.md <<'EOF'
Use this repository as the baseline implementation.

Next phase:
- OAuth integrations
- Spotify distributor workflow
- YouTube upload workflow
- Apple Music metadata export
- Scheduler
- AI orchestration
- Production deployment
EOF

echo "Done."
echo "Run:"
echo "./scripts/dev/aion-doctor.sh"
echo "make test"
echo "make api"
