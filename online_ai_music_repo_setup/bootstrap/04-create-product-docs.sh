#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

create_doc() {
  local path="$1"
  local title="$2"
  local purpose="$3"

  write_file_if_missing "${AION_ROOT}/${path}" "$(cat <<EOF
# ${title}

## Purpose

${purpose}

## Status

Draft

## Required Sections

1. Context
2. Goals
3. Non-goals
4. Stakeholders
5. Assumptions
6. Functional requirements
7. Non-functional requirements
8. Risks
9. Acceptance criteria
10. Open questions
11. Decision history

## Initial Constraints

- Content must be original or properly licensed.
- Metadata must not make unsupported medical claims.
- Publication must use supported APIs or approved manual workflows.
- Human approval is required before public release.
- The system must not automate artificial streams, fake engagement or platform manipulation.
EOF
)"
}

create_doc \
  "docs/00-overview/vision.md" \
  "Vision" \
  "Define the long-term product vision, values, boundaries and success criteria."

create_doc \
  "docs/00-overview/glossary.md" \
  "Glossary" \
  "Define canonical product, media, AI, platform and compliance terminology."

create_doc \
  "docs/01-product/prd.md" \
  "Product Requirements Document" \
  "Describe users, problems, outcomes, capabilities, scope and acceptance criteria."

create_doc \
  "docs/01-product/personas.md" \
  "Personas" \
  "Define owner, reviewer, publisher, analyst, administrator and future tenant personas."

create_doc \
  "docs/01-product/user-journeys.md" \
  "User Journeys" \
  "Describe end-to-end production, review, publication and analytics journeys."

create_doc \
  "docs/02-business/business-requirements.md" \
  "Business Requirements" \
  "Define monetization, operating model, cost controls, growth assumptions and business constraints."

create_doc \
  "docs/02-business/monetization.md" \
  "Monetization Model" \
  "Document platform revenue, licensing, SaaS and direct-sale models without guaranteeing income."

create_doc \
  "docs/03-requirements/srs.md" \
  "Software Requirements Specification" \
  "Maintain traceable functional and non-functional requirements."

create_doc \
  "docs/03-requirements/traceability-matrix.md" \
  "Requirements Traceability Matrix" \
  "Map requirements to services, APIs, tests and releases."

create_doc \
  "docs/12-roadmap/roadmap.md" \
  "Roadmap" \
  "Define phased delivery from personal-use MVP to optional multi-tenant SaaS."
