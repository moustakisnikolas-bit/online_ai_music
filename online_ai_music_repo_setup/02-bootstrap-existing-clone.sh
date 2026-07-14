#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /full/path/to/online_ai_music" >&2
  exit 1
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -d "${TARGET}/.git" ]] || {
  echo "ERROR: ${TARGET} is not a Git repository." >&2
  exit 1
}

AION_ROOT="$(cd "${TARGET}" && pwd)" \
DRY_RUN="${DRY_RUN:-0}" \
FORCE="${FORCE:-0}" \
bash "${SCRIPT_DIR}/bootstrap/00-bootstrap-aion.sh"

git -C "${TARGET}" status --short
echo "Bootstrap completed. Review changes before committing."
