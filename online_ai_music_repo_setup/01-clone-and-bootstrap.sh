#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/moustakisnikolas-bit/online_ai_music.git}"
TARGET_DIR="${TARGET_DIR:-online_ai_music}"
AUTO_COMMIT="${AUTO_COMMIT:-0}"
AUTO_PUSH="${AUTO_PUSH:-0}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v git >/dev/null 2>&1 || {
  echo "ERROR: git is required." >&2
  exit 1
}

if [[ -e "${TARGET_DIR}" && ! -d "${TARGET_DIR}/.git" ]]; then
  echo "ERROR: ${TARGET_DIR} exists but is not a Git repository." >&2
  exit 1
fi

if [[ ! -d "${TARGET_DIR}/.git" ]]; then
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "DRY RUN: git clone ${REPO_URL} ${TARGET_DIR}"
    mkdir -p "${TARGET_DIR}"
  else
    git clone "${REPO_URL}" "${TARGET_DIR}"
  fi
else
  echo "Using existing Git clone: ${TARGET_DIR}"
fi

AION_ROOT="$(cd "${TARGET_DIR}" && pwd)" DRY_RUN="${DRY_RUN}" FORCE="${FORCE}" bash "${SCRIPT_DIR}/bootstrap/00-bootstrap-aion.sh"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Dry run completed."
  exit 0
fi

git -C "${TARGET_DIR}" status --short

if [[ "${AUTO_COMMIT}" == "1" ]]; then
  git -C "${TARGET_DIR}" add .
  if git -C "${TARGET_DIR}" diff --cached --quiet; then
    echo "No staged changes to commit."
  else
    git -C "${TARGET_DIR}" commit -m "Bootstrap AION repository structure"
  fi
fi

if [[ "${AUTO_PUSH}" == "1" ]]; then
  if [[ "${AUTO_COMMIT}" != "1" ]]; then
    echo "ERROR: AUTO_PUSH=1 requires AUTO_COMMIT=1." >&2
    exit 1
  fi
  branch="$(git -C "${TARGET_DIR}" branch --show-current)"
  [[ -n "${branch}" ]] || branch="main"
  git -C "${TARGET_DIR}" push -u origin "${branch}"
fi

echo
echo "Repository bootstrap completed."
echo "Review with: cd ${TARGET_DIR} && git status"
