#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"
mkdir -p scripts/dev

cat > scripts/dev/install-python-312-macos.sh <<'EOF'
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
    echo "Install Homebrew first from https://brew.sh and rerun this script." >&2
    exit 1
  fi

  echo "Python 3.12 was not found."
  echo "Installing python@3.12 with Homebrew..."
  brew install python@3.12

  PYTHON_312="$(find_python_312 || true)"
fi

if [[ -z "${PYTHON_312}" ]]; then
  echo "ERROR: Python 3.12 could not be located after installation." >&2
  exit 1
fi

echo "Using Python:"
"${PYTHON_312}" --version
echo "Path: ${PYTHON_312}"

if [[ -d .venv ]]; then
  EXISTING_VERSION="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
      2>/dev/null || true
  )"

  if [[ "${EXISTING_VERSION}" != "3.12" ]]; then
    BACKUP=".venv-python-${EXISTING_VERSION:-unknown}-$(date +%Y%m%d-%H%M%S)"
    echo "Existing .venv uses Python ${EXISTING_VERSION:-unknown}."
    echo "Moving it to ${BACKUP}..."
    mv .venv "${BACKUP}"
  fi
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv with Python 3.12..."
  "${PYTHON_312}" -m venv .venv
fi

echo "Upgrading pip, setuptools and wheel..."
.venv/bin/python -m pip install --upgrade pip setuptools wheel

echo "Installing AION dependencies..."
.venv/bin/python -m pip install -e ".[dev]"

echo
echo "Environment ready:"
.venv/bin/python --version
.venv/bin/pytest --version

echo
echo "Running tests..."
PYTHONPATH=apps/api:apps/worker .venv/bin/pytest
EOF

chmod +x scripts/dev/install-python-312-macos.sh

cat > scripts/dev/setup-python-env.sh <<'EOF'
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
  echo "Python 3.12 is missing."
  echo "Run: ./scripts/dev/install-python-312-macos.sh"
  exit 1
fi

if [[ -d .venv ]]; then
  VENV_VERSION="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
      2>/dev/null || true
  )"

  if [[ "${VENV_VERSION}" != "3.12" ]]; then
    echo "ERROR: Existing .venv uses Python ${VENV_VERSION:-unknown}." >&2
    echo "Run: ./scripts/dev/install-python-312-macos.sh" >&2
    exit 1
  fi
else
  "${PYTHON_BIN}" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]"

echo "Python environment is ready."
.venv/bin/python --version
EOF

chmod +x scripts/dev/setup-python-env.sh

cat > Makefile <<'EOF'
.PHONY: help setup setup-macos install test lint api worker infra-up infra-down migrate doctor

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
EOF

echo "Update 006B applied successfully."
echo
echo "Now run:"
echo "  cd \"${TARGET}\""
echo "  make setup-macos"
