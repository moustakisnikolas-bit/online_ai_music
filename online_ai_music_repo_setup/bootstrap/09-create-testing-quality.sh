#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/docs/10-quality/test-strategy.md" "$(cat <<'EOF'
# Test Strategy

## Test Levels

- unit tests for domain logic;
- contract tests for APIs and events;
- integration tests for storage, queues and providers;
- end-to-end tests for production workflows;
- golden-file tests for media metadata;
- manual quality review for audio and visual assets;
- policy and compliance test cases.

## Critical Scenarios

- duplicate job submission;
- worker retry after partial output;
- publishing approval revocation;
- credential expiration;
- provider outage;
- storage failure;
- metadata validation;
- provenance loss prevention;
- cost-budget enforcement.
EOF
)"

write_file_if_missing "${AION_ROOT}/docs/10-quality/definition-of-done.md" "$(cat <<'EOF'
# Definition of Done

A change is done only when:

- acceptance criteria are satisfied;
- tests pass;
- security and privacy implications are reviewed;
- logs and metrics are defined;
- documentation is updated;
- migrations are reversible;
- failure behavior is tested;
- public publishing remains approval-controlled.
EOF
)"

write_file_if_missing "${AION_ROOT}/.pre-commit-config.yaml" "$(cat <<'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: detect-private-key
      - id: check-merge-conflict
EOF
)"
