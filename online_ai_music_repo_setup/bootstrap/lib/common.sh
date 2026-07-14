#!/usr/bin/env bash
set -Eeuo pipefail

AION_ROOT="${AION_ROOT:-$(pwd)}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
AION_LOG_DIR="${AION_ROOT}/.aion/logs"
mkdir -p "${AION_LOG_DIR}"
AION_LOG_FILE="${AION_LOG_DIR}/bootstrap-$(date +%Y%m%d-%H%M%S).log"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${AION_LOG_FILE}"
}

die() {
  log "ERROR: $*"
  exit 1
}

run_cmd() {
  log "RUN: $*"
  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi
  "$@"
}

ensure_dir() {
  local path="$1"
  if [[ ! -d "${path}" ]]; then
    run_cmd mkdir -p "${path}"
  fi
}

write_file_if_missing() {
  local path="$1"
  local content="$2"
  ensure_dir "$(dirname "${path}")"

  if [[ -e "${path}" && -s "${path}" && "${FORCE}" != "1" ]]; then
    log "SKIP existing file: ${path}"
    return 0
  fi

  log "WRITE: ${path}"
  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi
  printf '%s\n' "${content}" > "${path}"
}

append_line_if_missing() {
  local path="$1"
  local line="$2"
  ensure_dir "$(dirname "${path}")"
  touch "${path}"

  if ! grep -Fqx "${line}" "${path}"; then
    log "APPEND: ${line} -> ${path}"
    if [[ "${DRY_RUN}" != "1" ]]; then
      printf '%s\n' "${line}" >> "${path}"
    fi
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  command_exists "$1" || die "Required command not found: $1"
}
