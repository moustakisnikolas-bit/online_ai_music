#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

find_python_312() {
  local candidate

  for candidate in \
    python3.12 \
    /opt/homebrew/bin/python3.12 \
    /usr/local/bin/python3.12 \
    /opt/homebrew/opt/python@3.12/bin/python3.12 \
    /usr/local/opt/python@3.12/bin/python3.12; do
    if [[ -x "${candidate}" ]] || command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done

  return 1
}

PYTHON_312="$(find_python_312 || true)"

if [[ -z "${PYTHON_312}" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "ERROR: Homebrew is not installed." >&2
    exit 1
  fi

  echo "Installing Python 3.12 with Homebrew..."
  brew install python@3.12
  PYTHON_312="$(find_python_312 || true)"
fi

if [[ -z "${PYTHON_312}" ]]; then
  echo "ERROR: Python 3.12 could not be located." >&2
  exit 1
fi

echo "Using:"
"${PYTHON_312}" --version
echo "Path: ${PYTHON_312}"

if [[ -d .venv ]]; then
  EXISTING_VERSION="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
      2>/dev/null || true
  )"

  if [[ "${EXISTING_VERSION}" != "3.12" ]]; then
    BACKUP=".venv-python-${EXISTING_VERSION:-unknown}-$(date +%Y%m%d-%H%M%S)"
    echo "Moving incompatible .venv to ${BACKUP}"
    mv .venv "${BACKUP}"
  fi
fi

if [[ ! -d .venv ]]; then
  "${PYTHON_312}" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements/dev.txt

echo
echo "Environment ready:"
.venv/bin/python --version
.venv/bin/pytest --version

echo
echo "Running tests..."
PYTHONPATH=apps/api:apps/worker .venv/bin/pytest
