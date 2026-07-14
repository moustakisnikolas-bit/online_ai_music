#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${1:-online_ai_music}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Bootstrap AION repository structure}"

[[ -d "${TARGET_DIR}/.git" ]] || {
  echo "ERROR: ${TARGET_DIR} is not a Git repository." >&2
  exit 1
}

echo "Current changes:"
git -C "${TARGET_DIR}" status --short

echo
read -r -p "Stage, commit and push these changes? [y/N] " answer
case "${answer}" in
  y|Y|yes|YES)
    git -C "${TARGET_DIR}" add .
    git -C "${TARGET_DIR}" commit -m "${COMMIT_MESSAGE}"
    branch="$(git -C "${TARGET_DIR}" branch --show-current)"
    [[ -n "${branch}" ]] || branch="main"
    git -C "${TARGET_DIR}" push -u origin "${branch}"
    ;;
  *)
    echo "Cancelled. No Git changes were made by this script."
    ;;
esac
