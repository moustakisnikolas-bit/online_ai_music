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

PYTHON_BIN="${PYTHON_BIN:-$(find_python_312 || true)}"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: Python 3.12 is missing." >&2
  echo "Run: make setup-macos" >&2
  exit 1
fi

if [[ -d .venv ]]; then
  VENV_VERSION="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
      2>/dev/null || true
  )"

  if [[ "${VENV_VERSION}" != "3.12" ]]; then
    echo "ERROR: Existing .venv uses Python ${VENV_VERSION:-unknown}." >&2
    echo "Run: make setup-macos" >&2
    exit 1
  fi
else
  "${PYTHON_BIN}" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements/dev.txt

echo "Python environment is ready."
