#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

ensure_dir "${AION_ROOT}"

if [[ ! -d "${AION_ROOT}/.git" ]]; then
  require_command git
  run_cmd git -C "${AION_ROOT}" init
else
  log "Git repository already exists."
fi

write_file_if_missing "${AION_ROOT}/.gitignore" "$(cat <<'EOF'
# OS
.DS_Store
Thumbs.db

# IDE
.vscode/*
!.vscode/extensions.json
!.vscode/settings.example.json
.idea/

# Secrets
.env
.env.*
!.env.example
*.pem
*.key
secrets/
!.gitkeep

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
build/
.next/
coverage/

# Logs and runtime
*.log
logs/
tmp/
temp/
.aion/logs/

# Media outputs
data/generated/
data/cache/
artifacts/
renders/

# Infrastructure
.terraform/
*.tfstate
*.tfstate.*
charts/**/charts/

# Local databases
*.db
*.sqlite
*.sqlite3
EOF
)"

write_file_if_missing "${AION_ROOT}/.editorconfig" "$(cat <<'EOF'
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.py]
indent_size = 4

[Makefile]
indent_style = tab
EOF
)"

write_file_if_missing "${AION_ROOT}/.env.example" "$(cat <<'EOF'
AION_ENV=development
AION_LOG_LEVEL=INFO
DATABASE_URL=postgresql://aion:aion@localhost:5432/aion
REDIS_URL=redis://localhost:6379/0
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=aion
OBJECT_STORAGE_SECRET_KEY=change-me
OPENROUTER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
EOF
)"
