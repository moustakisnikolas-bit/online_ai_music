#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

failed=0

check_command() {
  local cmd="$1"
  if command -v "${cmd}" >/dev/null 2>&1; then
    echo "OK: ${cmd}"
  else
    echo "MISSING: ${cmd}"
    failed=1
  fi
}

check_command git
check_command docker
check_command python3

if [[ -x .venv/bin/python ]]; then
  echo "OK: .venv/bin/python"
  .venv/bin/python --version
else
  echo "MISSING: .venv/bin/python"
  failed=1
fi

if [[ -x .venv/bin/pytest ]]; then
  echo "OK: .venv/bin/pytest"
else
  echo "MISSING: .venv/bin/pytest"
  failed=1
fi

if [[ "${failed}" == "1" ]]; then
  echo
  echo "Local environment is incomplete."
  echo "Run: ./scripts/dev/setup-python-env.sh"
  exit 1
fi

echo "Local environment is valid."
