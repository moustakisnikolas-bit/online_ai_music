#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

required_paths=(
  "${AION_ROOT}/README.md"
  "${AION_ROOT}/AGENTS.md"
  "${AION_ROOT}/docs/01-product/prd.md"
  "${AION_ROOT}/docs/03-requirements/srs.md"
  "${AION_ROOT}/docs/04-architecture/architecture.md"
  "${AION_ROOT}/architecture/adrs/ADR-0001-modular-monolith-first.md"
  "${AION_ROOT}/docker-compose.yml"
  "${AION_ROOT}/scripts/validate.sh"
)

failed=0
for path in "${required_paths[@]}"; do
  if [[ ! -f "${path}" ]]; then
    log "MISSING: ${path}"
    failed=1
  else
    log "OK: ${path}"
  fi
done

if [[ "${failed}" == "1" ]]; then
  die "Repository validation failed."
fi

log "Repository validation completed successfully."
