#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

log "Starting AION repository bootstrap"
log "Target directory: ${AION_ROOT}"

scripts=(
  "01-init-git.sh"
  "02-create-repository-structure.sh"
  "03-create-governance-docs.sh"
  "04-create-product-docs.sh"
  "05-create-architecture-docs.sh"
  "06-create-ai-context.sh"
  "07-create-service-templates.sh"
  "08-create-infrastructure.sh"
  "09-create-testing-quality.sh"
  "10-create-github-automation.sh"
  "11-validate-repository.sh"
)

for script in "${scripts[@]}"; do
  log "Executing ${script}"
  AION_ROOT="${AION_ROOT}" DRY_RUN="${DRY_RUN}" FORCE="${FORCE}" \
    bash "${SCRIPT_DIR}/${script}"
done

log "AION bootstrap completed successfully."
log "Next steps:"
log "1. Review README.md and docs/"
log "2. Run: git status"
log "3. Commit the generated baseline"
