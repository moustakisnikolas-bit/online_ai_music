#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/README.md" "$(cat <<'EOF'
# AION

**AION** is an AI-native operating system for building, operating and optimizing compliant digital content businesses.

The first factory is the **Ambient Media Factory**, which produces original ambient audio, artwork, video assets, metadata and publishing packages under human supervision.

## Core Principles

- Original content by default
- Human approval before publication
- Compliance-first architecture
- Modular factories and integrations
- Vendor-neutral AI orchestration
- Full auditability and cost visibility

## Repository Map

- `apps/`: user-facing and administrative applications
- `services/`: independently deployable domain services
- `packages/`: shared libraries and SDKs
- `docs/`: product, architecture and operational documentation
- `architecture/`: ADRs, RFCs and diagrams
- `api/`: OpenAPI and AsyncAPI contracts
- `database/`: schemas and migrations
- `prompts/`: versioned AI instructions
- `workflows/`: orchestration definitions
- `infrastructure/`: container and cloud deployment
- `.aion/`: project context and AI-agent rules

## Current Status

Documentation-first bootstrap. No production claims should be made until the architecture, compliance review, tests and platform integrations have been validated.
EOF
)"

write_file_if_missing "${AION_ROOT}/CONTRIBUTING.md" "$(cat <<'EOF'
# Contributing

1. Read `.aion/context/project.md`.
2. Read applicable ADRs and coding standards.
3. Create a focused branch.
4. Add or update tests.
5. Update documentation and contracts.
6. Submit a pull request with risks and validation evidence.

No contributor or AI agent may bypass approval, audit, copyright or compliance controls.
EOF
)"

write_file_if_missing "${AION_ROOT}/SECURITY.md" "$(cat <<'EOF'
# Security Policy

Do not commit credentials, customer data or private platform tokens.

Report vulnerabilities privately to the repository owner.

Critical security requirements:
- least privilege;
- encrypted secrets;
- auditable access;
- dependency scanning;
- signed release artifacts where practical;
- human approval for publishing and destructive actions.
EOF
)"

write_file_if_missing "${AION_ROOT}/CODE_OF_CONDUCT.md" "$(cat <<'EOF'
# Code of Conduct

Contributors must communicate respectfully, document decisions, disclose uncertainty and avoid deceptive or non-compliant implementation practices.
EOF
)"

write_file_if_missing "${AION_ROOT}/CHANGELOG.md" "$(cat <<'EOF'
# Changelog

All notable project changes will be documented here.

## [Unreleased]

### Added
- Initial repository bootstrap.
EOF
)"
