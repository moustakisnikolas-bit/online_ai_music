#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

mkdir -p "$TARGET/docs/01-product"
mkdir -p "$TARGET/docs/02-business"
mkdir -p "$TARGET/docs/03-requirements"

cat > "$TARGET/docs/01-product/vision.md" <<'EOF'
# AION Vision

## Mission
Build an AI-native operating system that enables a single creator or team to build compliant digital media businesses using AI-assisted workflows.

## Principles
- Human approval before publishing
- Original content
- Compliance-first
- Modular architecture
- Observable systems
- Replaceable AI providers

## Initial Factory
Ambient Media Factory
EOF

cat > "$TARGET/docs/02-business/business-requirements.md" <<'EOF'
# Business Requirements

## Business Goal
Create a sustainable media business based on original ambient audio and related digital assets.

## Revenue Sources
- Streaming royalties
- Video monetization
- Digital downloads
- Licensing
- Future SaaS subscriptions

## Constraints
- Respect platform policies.
- No fake engagement or stream manipulation.
- Maintain provenance for generated assets.
EOF

cat > "$TARGET/docs/03-requirements/srs.md" <<'EOF'
# Software Requirements Specification (Initial)

## Functional Requirements

FR-001 Create projects
FR-002 Generate original audio
FR-003 Produce artwork
FR-004 Produce videos
FR-005 Generate metadata
FR-006 Support review workflow
FR-007 Publish through approved workflows
FR-008 Track analytics

## Non-Functional Requirements

- Security
- Auditability
- Scalability
- Cost visibility
- Extensibility
EOF

echo "Update 001 applied successfully."
