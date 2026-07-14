#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/docs/04-architecture/system-context.md" "$(cat <<'EOF'
# System Context

AION coordinates people, AI providers, media-processing workers, storage, analytics providers, distribution services and public platforms.

## External Actors

- Owner
- Reviewer
- Publisher
- Platform administrator
- AI model providers
- Music distributor
- YouTube
- Analytics and revenue data providers
- Object storage
- Notification providers

## Trust Boundaries

Every external integration must be treated as untrusted, authenticated, rate-limited, logged and isolated.
EOF
)"

write_file_if_missing "${AION_ROOT}/docs/04-architecture/architecture.md" "$(cat <<'EOF'
# Architecture

## Architectural Style

- modular monolith for the first production milestone;
- well-defined domain boundaries;
- asynchronous job execution;
- event contracts from the beginning;
- extraction into services only when justified by scale or team ownership.

## Core Domains

1. Identity and access
2. Projects and brands
3. Asset registry
4. Audio production
5. Image production
6. Video production
7. Metadata and localization
8. Workflow orchestration
9. Review and approval
10. Distribution and publishing
11. Analytics and revenue
12. AI routing and governance
13. Compliance and audit

## Mandatory Cross-Cutting Controls

- correlation IDs;
- idempotency keys;
- audit events;
- quotas;
- cost accounting;
- retry and dead-letter handling;
- content provenance;
- approval state machine.
EOF
)"

write_file_if_missing "${AION_ROOT}/architecture/adrs/ADR-0001-modular-monolith-first.md" "$(cat <<'EOF'
# ADR-0001: Start with a Modular Monolith

## Status

Accepted

## Context

AION requires many capabilities, but the initial owner is a small team or individual. Premature microservices would increase operational cost and coordination risk.

## Decision

Implement the first production version as a modular monolith with isolated domain modules, background workers and versioned contracts.

## Consequences

Positive:
- faster delivery;
- simpler local development;
- lower infrastructure cost.

Negative:
- discipline is required to preserve boundaries;
- some modules may later require extraction.
EOF
)"

write_file_if_missing "${AION_ROOT}/architecture/diagrams/system-context.mmd" "$(cat <<'EOF'
flowchart LR
  Owner[Owner / Reviewer] --> Web[AION Web Application]
  Web --> API[AION API]
  API --> DB[(PostgreSQL)]
  API --> Queue[(Job Queue)]
  Queue --> Workers[Media & AI Workers]
  Workers --> Storage[(Object Storage)]
  Workers --> AI[AI Providers]
  API --> Distributor[Music Distributor]
  API --> YouTube[YouTube]
  API --> Analytics[Analytics Providers]
EOF
)"
