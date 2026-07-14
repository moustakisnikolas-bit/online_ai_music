#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

mkdir -p requirements
mkdir -p scripts/dev

cat > requirements/runtime.txt <<'EOF'
fastapi>=0.115,<1.0
uvicorn[standard]>=0.34,<1.0
sqlalchemy>=2.0,<3.0
psycopg[binary]>=3.2,<4.0
alembic>=1.14,<2.0
pydantic>=2.10,<3.0
pydantic-settings>=2.7,<3.0
redis>=5.2,<6.0
minio>=7.2,<8.0
httpx>=0.28,<1.0
EOF

cat > requirements/dev.txt <<'EOF'
-r runtime.txt
pytest>=8.3,<9.0
pytest-asyncio>=0.25,<1.0
ruff>=0.9,<1.0
mypy>=1.14,<2.0
EOF

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
EOF

chmod +x scripts/dev/setup-python-env.sh

cat > pyproject.toml <<'EOF'
[project]
name = "aion-monorepo"
version = "0.1.0"
description = "AI Autonomous Content Operating System"
requires-python = ">=3.12"
dynamic = ["dependencies"]

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = []

[tool.pytest.ini_options]
pythonpath = ["apps/api", "apps/worker"]
testpaths = ["apps/api/tests", "apps/worker/tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
EOF

echo "Update 006C applied successfully."
echo
echo "Now run:"
echo "  cd \"${TARGET}\""
echo "  make setup-macos"
