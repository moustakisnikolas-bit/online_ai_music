#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

mkdir -p scripts/dev

cat > scripts/dev/setup-python-env.sh <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

find_python() {
  for candidate in python3.12 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="${PYTHON_BIN:-$(find_python || true)}"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: Python was not found." >&2
  echo "Install Python 3.12 and run this script again." >&2
  exit 1
fi

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_MAJOR="$("${PYTHON_BIN}" -c 'import sys; print(sys.version_info.major)')"
PYTHON_MINOR="$("${PYTHON_BIN}" -c 'import sys; print(sys.version_info.minor)')"

echo "Using ${PYTHON_BIN} (${PYTHON_VERSION})"

if [[ "${PYTHON_MAJOR}" -lt 3 ]] || [[ "${PYTHON_MAJOR}" -eq 3 && "${PYTHON_MINOR}" -lt 12 ]]; then
  echo "ERROR: AION currently requires Python 3.12 or newer." >&2
  echo "Detected Python ${PYTHON_VERSION}." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv..."
  "${PYTHON_BIN}" -m venv .venv
else
  echo ".venv already exists."
fi

echo "Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip

echo "Installing AION and development dependencies..."
.venv/bin/python -m pip install -e ".[dev]"

echo
echo "Python environment is ready."
echo "Run:"
echo "  make test"
EOF

chmod +x scripts/dev/setup-python-env.sh

cat > scripts/dev/doctor-local.sh <<'EOF'
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
EOF

chmod +x scripts/dev/doctor-local.sh

cat > Makefile <<'EOF'
.PHONY: help setup install test lint api worker infra-up infra-down migrate doctor

help:
	@echo "AION commands"
	@echo "  make setup"
	@echo "  make install"
	@echo "  make test"
	@echo "  make lint"
	@echo "  make api"
	@echo "  make worker"
	@echo "  make infra-up"
	@echo "  make infra-down"
	@echo "  make migrate"
	@echo "  make doctor"

setup:
	./scripts/dev/setup-python-env.sh

install: setup

test:
	@if [ ! -x .venv/bin/pytest ]; then \
		echo "Python environment missing. Run: make setup"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/pytest

lint:
	@if [ ! -x .venv/bin/ruff ]; then \
		echo "Python environment missing. Run: make setup"; \
		exit 1; \
	fi
	.venv/bin/ruff check apps

api:
	@if [ ! -x .venv/bin/uvicorn ]; then \
		echo "Python environment missing. Run: make setup"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --reload

worker:
	@if [ ! -x .venv/bin/python ]; then \
		echo "Python environment missing. Run: make setup"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api:apps/worker .venv/bin/python apps/worker/app/main.py

infra-up:
	docker compose up -d --build

infra-down:
	docker compose down

migrate:
	@if [ ! -x .venv/bin/alembic ]; then \
		echo "Python environment missing. Run: make setup"; \
		exit 1; \
	fi
	PYTHONPATH=apps/api .venv/bin/alembic upgrade head

doctor:
	./tools/aion/aion doctor
	./scripts/dev/doctor-local.sh
EOF

echo "Update 006A applied successfully."
echo
echo "Next commands:"
echo "  cd \"${TARGET}\""
echo "  make setup"
echo "  make test"
