#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/AGENTS.md" "$(cat <<'EOF'
# Instructions for AI Coding Agents

Before making changes:

1. Read `.aion/context/project.md`.
2. Read `.aion/context/constraints.md`.
3. Read applicable files under `.aion/rules/`.
4. Inspect current tests and contracts.
5. Make the smallest coherent change.
6. Never invent integration capabilities.
7. Never claim platform compliance without evidence.
8. Never automate fake engagement, stream manipulation or unsupported medical claims.
9. Preserve human approval for public publishing.
10. Update documentation and tests with implementation changes.
EOF
)"

write_file_if_missing "${AION_ROOT}/.aion/context/project.md" "$(cat <<'EOF'
# Project Context

AION is an AI-native content operations platform.

Initial goal:
Help one owner produce and monetize original ambient audio and related media on legitimate platforms.

Long-term goal:
Provide reusable factories for additional digital content businesses.

The platform is not intended to exploit royalty thresholds, simulate users, generate fake streams or evade platform controls.
EOF
)"

write_file_if_missing "${AION_ROOT}/.aion/context/constraints.md" "$(cat <<'EOF'
# Constraints

- Start cost-conscious and local-development friendly.
- Prefer open standards and replaceable providers.
- Use supported platform APIs and distributor workflows.
- Store provenance for generated and licensed assets.
- Require review gates before publication.
- Health-related content may be described as relaxation or meditation content, not treatment.
- No copying of recognizable artists, recordings, brands or protected visual styles.
EOF
)"

rules=(
  "architecture-rules.md"
  "coding-standards.md"
  "security-rules.md"
  "testing-rules.md"
  "documentation-rules.md"
  "prompt-rules.md"
  "media-compliance-rules.md"
)

for rule in "${rules[@]}"; do
  title="$(echo "${rule%.md}" | tr '-' ' ')"
  write_file_if_missing "${AION_ROOT}/.aion/rules/${rule}" "# ${title}

- Prefer explicit, testable behavior.
- Document assumptions and uncertainty.
- Maintain backwards-compatible contracts where feasible.
- Do not hide errors or silently bypass controls.
- Add validation, observability and tests for critical paths.
"
done
