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
