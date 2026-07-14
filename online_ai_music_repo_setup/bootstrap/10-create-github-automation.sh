#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/.github/pull_request_template.md" "$(cat <<'EOF'
## Summary

## Requirement / Issue

## Changes

## Validation

## Risks

## Security and Compliance

## Documentation Updated

- [ ] Yes
- [ ] Not required, with explanation
EOF
)"

write_file_if_missing "${AION_ROOT}/.github/ISSUE_TEMPLATE/feature.md" "$(cat <<'EOF'
---
name: Feature
about: Propose a traceable product capability
---

## Problem

## Desired Outcome

## Requirements

## Acceptance Criteria

## Risks and Constraints
EOF
)"

write_file_if_missing "${AION_ROOT}/.github/workflows/validate.yml" "$(cat <<'EOF'
name: Validate Repository

on:
  push:
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate baseline
        run: bash scripts/validate.sh
EOF
)"
