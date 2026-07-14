#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

services=(
  "identity"
  "projects"
  "asset-registry"
  "audio-engine"
  "frequency-engine"
  "image-engine"
  "video-engine"
  "metadata-engine"
  "workflow-engine"
  "review-approval"
  "publishing"
  "analytics"
  "ai-router"
  "notifications"
  "audit"
)

for service in "${services[@]}"; do
  dir="${AION_ROOT}/services/${service}"
  ensure_dir "${dir}/src"
  ensure_dir "${dir}/tests"
  write_file_if_missing "${dir}/README.md" "# ${service}

## Responsibility

Define one clear bounded responsibility for this module.

## Required Documentation

- API contract
- events
- configuration
- storage ownership
- failure modes
- security model
- test strategy
- observability
"
  write_file_if_missing "${dir}/API.md" "# API

No API has been approved yet. Define contracts before implementation.
"
  write_file_if_missing "${dir}/EVENTS.md" "# Events

Document produced and consumed events with schema versions and idempotency behavior.
"
  write_file_if_missing "${dir}/CONFIG.md" "# Configuration

All secrets must be injected through approved secret management.
"
  write_file_if_missing "${dir}/TESTING.md" "# Testing

Cover unit, contract, integration, failure and authorization scenarios.
"
done
