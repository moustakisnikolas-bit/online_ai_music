#!/usr/bin/env bash
set -Eeuo pipefail

AION_ROOT="${AION_ROOT:-$(pwd)}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "[AION] $*"
}

slug_is_valid() {
  case "$1" in
    ""|*[!a-z0-9-]*|-*|*-|*--*)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

require_valid_slug() {
  local value="$1"
  local label="$2"

  slug_is_valid "${value}" || die "${label} must use lowercase letters, numbers and single hyphens only."
}

title_from_slug() {
  echo "$1" | awk -F- '{
    for (i = 1; i <= NF; i++) {
      $i = toupper(substr($i,1,1)) substr($i,2)
    }
    OFS=" "
    print $0
  }'
}

write_file() {
  local path="$1"
  local force="$2"
  local content="$3"

  mkdir -p "$(dirname "${path}")"

  if [[ -e "${path}" && "${force}" != "1" ]]; then
    die "File already exists: ${path}. Use --force to overwrite."
  fi

  printf '%s\n' "${content}" > "${path}"
  info "Created ${path#${AION_ROOT}/}"
}

next_adr_number() {
  local max="0"
  local file
  local base
  local number

  for file in "${AION_ROOT}"/architecture/adrs/ADR-*.md; do
    [[ -e "${file}" ]] || continue
    base="$(basename "${file}")"
    number="$(echo "${base}" | sed -E 's/^ADR-([0-9]{4}).*/\1/')"
    case "${number}" in
      *[!0-9]*|"")
        continue
        ;;
    esac
    number=$((10#${number}))
    if [[ "${number}" -gt "${max}" ]]; then
      max="${number}"
    fi
  done

  printf '%04d\n' $((max + 1))
}
