#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

mkdir -p scripts/dev
mkdir -p scripts/ops
mkdir -p docs/11-operations
mkdir -p tests/e2e

cat > scripts/dev/docker-smoke-test.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
MAX_READY_ATTEMPTS="${MAX_READY_ATTEMPTS:-60}"
MAX_JOB_ATTEMPTS="${MAX_JOB_ATTEMPTS:-60}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: Required command not found: $1" >&2
    exit 1
  }
}

require_command docker
require_command curl
require_command python3

echo "Starting AION Docker stack..."
docker compose up -d --build

echo
echo "Waiting for API readiness..."

attempt=1
while [[ "${attempt}" -le "${MAX_READY_ATTEMPTS}" ]]; do
  if curl --silent --fail "${API_BASE_URL}/health" >/dev/null 2>&1; then
    echo "API is ready."
    break
  fi

  if [[ "${attempt}" -eq "${MAX_READY_ATTEMPTS}" ]]; then
    echo "ERROR: API did not become ready." >&2
    docker compose ps
    docker compose logs --tail=200 api migrate worker
    exit 1
  fi

  sleep "${SLEEP_SECONDS}"
  attempt=$((attempt + 1))
done

PROJECT_SLUG="aion-smoke-$(date +%Y%m%d%H%M%S)"
PROJECT_PAYLOAD="$(cat <<JSON
{
  "name": "AION Docker Smoke Test",
  "slug": "${PROJECT_SLUG}"
}
JSON
)"

echo
echo "Creating project..."
PROJECT_RESPONSE="$(
  curl --silent --fail \
    -X POST \
    -H "Content-Type: application/json" \
    -d "${PROJECT_PAYLOAD}" \
    "${API_BASE_URL}/api/v1/projects"
)"

PROJECT_ID="$(
  printf '%s' "${PROJECT_RESPONSE}" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print(payload["id"])
'
)"

echo "Project ID: ${PROJECT_ID}"

JOB_PAYLOAD="$(cat <<JSON
{
  "project_id": "${PROJECT_ID}",
  "title": "AION Docker 432 Hz Smoke Test",
  "frequency_hz": 432,
  "duration_seconds": 2,
  "sample_rate": 8000,
  "amplitude": 0.1
}
JSON
)"

echo
echo "Submitting audio job..."
JOB_RESPONSE="$(
  curl --silent --fail \
    -X POST \
    -H "Content-Type: application/json" \
    -d "${JOB_PAYLOAD}" \
    "${API_BASE_URL}/api/v1/audio/jobs"
)"

JOB_ID="$(
  printf '%s' "${JOB_RESPONSE}" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print(payload["id"])
'
)"

echo "Job ID: ${JOB_ID}"
echo
echo "Polling job status..."

attempt=1
FINAL_RESPONSE=""

while [[ "${attempt}" -le "${MAX_JOB_ATTEMPTS}" ]]; do
  FINAL_RESPONSE="$(
    curl --silent --fail \
      "${API_BASE_URL}/api/v1/audio/jobs/${JOB_ID}"
  )"

  STATUS="$(
    printf '%s' "${FINAL_RESPONSE}" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print(payload["status"])
'
  )"

  echo "Attempt ${attempt}: ${STATUS}"

  case "${STATUS}" in
    completed)
      break
      ;;
    failed|queue_failed)
      echo "ERROR: Audio job failed." >&2
      printf '%s\n' "${FINAL_RESPONSE}"
      docker compose logs --tail=200 worker api
      exit 1
      ;;
  esac

  if [[ "${attempt}" -eq "${MAX_JOB_ATTEMPTS}" ]]; then
    echo "ERROR: Audio job did not complete in time." >&2
    printf '%s\n' "${FINAL_RESPONSE}"
    docker compose logs --tail=200 worker api
    exit 1
  fi

  sleep "${SLEEP_SECONDS}"
  attempt=$((attempt + 1))
done

OUTPUT_PATH="$(
  printf '%s' "${FINAL_RESPONSE}" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print(payload["output_file_path"] or "")
'
)"

if [[ -z "${OUTPUT_PATH}" ]]; then
  echo "ERROR: Completed job has no output path." >&2
  exit 1
fi

OUTPUT_FILENAME="$(basename "${OUTPUT_PATH}")"
LOCAL_OUTPUT="${ROOT}/data/generated/audio/${OUTPUT_FILENAME}"

if [[ ! -f "${LOCAL_OUTPUT}" ]]; then
  echo "ERROR: Generated file not found locally: ${LOCAL_OUTPUT}" >&2
  docker compose logs --tail=200 worker
  exit 1
fi

python3 - "${LOCAL_OUTPUT}" <<'PY'
import sys
import wave
from pathlib import Path

path = Path(sys.argv[1])

with wave.open(str(path), "rb") as wav_file:
    assert wav_file.getnchannels() == 1
    assert wav_file.getframerate() == 8000
    assert wav_file.getnframes() == 16000

print(f"Validated WAV file: {path}")
PY

echo
echo "Docker services:"
docker compose ps

echo
echo "AION Docker smoke test passed."
echo "Generated asset:"
echo "  ${LOCAL_OUTPUT}"
EOF

chmod +x scripts/dev/docker-smoke-test.sh

cat > scripts/ops/docker-reset-local.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo "This will stop containers and remove local Docker volumes."
echo "Generated files under data/generated will not be deleted."
echo
read -r -p "Continue? [y/N] " answer

case "${answer}" in
  y|Y|yes|YES)
    docker compose down --volumes --remove-orphans
    echo "Local Docker stack and volumes removed."
    ;;
  *)
    echo "Cancelled."
    ;;
esac
EOF

chmod +x scripts/ops/docker-reset-local.sh

cat > tests/e2e/README.md <<'EOF'
# End-to-End Tests

The first AION end-to-end test runs against the complete local Docker stack.

Run:

```bash
./scripts/dev/docker-smoke-test.sh
```

The test validates:

1. PostgreSQL startup
2. Redis startup
3. Alembic migrations
4. FastAPI readiness
5. Project persistence
6. Audio job persistence
7. Redis queue delivery
8. Worker processing
9. WAV output creation
10. WAV header and duration
EOF

cat > docs/11-operations/docker-local-stack.md <<'EOF'
# Local Docker Stack

## Components

- PostgreSQL
- Redis
- MinIO
- Alembic migration container
- FastAPI API
- Audio worker

## Start

```bash
docker compose up -d --build
```

## Status

```bash
docker compose ps
```

## Logs

```bash
docker compose logs -f api worker migrate
```

## End-to-End Validation

```bash
./scripts/dev/docker-smoke-test.sh
```

## Stop

```bash
docker compose down
```

## Destructive Local Reset

```bash
./scripts/ops/docker-reset-local.sh
```

The reset helper asks for confirmation before deleting local Docker volumes.

## Expected Workflow

1. API accepts an audio job.
2. PostgreSQL stores the job.
3. Redis queues the job ID.
4. Worker claims the job.
5. Worker creates a WAV file.
6. Worker updates the job status to completed.
7. The generated file appears under `data/generated/audio`.
EOF

cat > Makefile <<'EOF'
.PHONY: help setup setup-macos install test lint api worker infra-up infra-down migrate doctor smoke reset-local

help:
	@echo "AION commands"
	@echo "  make setup-macos"
	@echo "  make setup"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make worker"
	@echo "  make infra-up"
	@echo "  make infra-down"
	@echo "  make migrate"
	@echo "  make doctor"
	@echo "  make smoke"
	@echo "  make reset-local"

setup-macos:
	./scripts/dev/install-python-312-macos.sh

setup:
	./scripts/dev/setup-python-env.sh

install: setup

test:
	@if [ ! -x .venv/bin/pytest ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/pytest

lint:
	@if [ ! -x .venv/bin/ruff ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	.venv/bin/ruff check apps

api:
	@if [ ! -x .venv/bin/uvicorn ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --reload

worker:
	@if [ ! -x .venv/bin/python ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/python apps/worker/app/main.py

infra-up:
	docker compose up -d --build

infra-down:
	docker compose down

migrate:
	@if [ ! -x .venv/bin/alembic ]; then \
		echo "Python environment missing. Run: make setup-macos"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/alembic upgrade head

doctor:
	./tools/aion/aion doctor
	./scripts/dev/doctor-local.sh

smoke:
	./scripts/dev/docker-smoke-test.sh

reset-local:
	./scripts/ops/docker-reset-local.sh
EOF

echo "Update 007 applied successfully."
echo
echo "Next:"
echo "  cd \"${TARGET}\""
echo "  make smoke"
