#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

mkdir -p "${TARGET}/tools/aion/lib"
mkdir -p "${TARGET}/tools/templates"
mkdir -p "${TARGET}/architecture/adrs"
mkdir -p "${TARGET}/workflows/definitions"
mkdir -p "${TARGET}/docs/generated"
mkdir -p "${TARGET}/services"

cat > "${TARGET}/tools/aion/lib/common.sh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

AION_ROOT="${AION_ROOT:-$(pwd)}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "[AION] $*"
}

slug_is_valid() {
  case "$1" in
    ""|*[!a-z0-9-]*|-*|*-|*--*)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

require_valid_slug() {
  local value="$1"
  local label="$2"

  slug_is_valid "${value}" || die "${label} must use lowercase letters, numbers and single hyphens only."
}

title_from_slug() {
  echo "$1" | awk -F- '{
    for (i = 1; i <= NF; i++) {
      $i = toupper(substr($i,1,1)) substr($i,2)
    }
    OFS=" "
    print $0
  }'
}

write_file() {
  local path="$1"
  local force="$2"
  local content="$3"

  mkdir -p "$(dirname "${path}")"

  if [[ -e "${path}" && "${force}" != "1" ]]; then
    die "File already exists: ${path}. Use --force to overwrite."
  fi

  printf '%s\n' "${content}" > "${path}"
  info "Created ${path#${AION_ROOT}/}"
}

next_adr_number() {
  local max="0"
  local file
  local base
  local number

  for file in "${AION_ROOT}"/architecture/adrs/ADR-*.md; do
    [[ -e "${file}" ]] || continue
    base="$(basename "${file}")"
    number="$(echo "${base}" | sed -E 's/^ADR-([0-9]{4}).*/\1/')"
    case "${number}" in
      *[!0-9]*|"")
        continue
        ;;
    esac
    number=$((10#${number}))
    if [[ "${number}" -gt "${max}" ]]; then
      max="${number}"
    fi
  done

  printf '%04d\n' $((max + 1))
}
EOF

cat > "${TARGET}/tools/aion/aion" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AION_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export AION_ROOT

source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
  cat <<'HELP'
AION CLI

Usage:
  ./tools/aion/aion help
  ./tools/aion/aion version
  ./tools/aion/aion doctor
  ./tools/aion/aion generate service <name> [--force]
  ./tools/aion/aion generate adr <slug> [--force]
  ./tools/aion/aion generate workflow <name> [--force]
  ./tools/aion/aion generate doc <section> <name> [--force]

Examples:
  ./tools/aion/aion generate service audio-engine
  ./tools/aion/aion generate adr use-postgresql
  ./tools/aion/aion generate workflow publish-youtube
  ./tools/aion/aion generate doc architecture storage-strategy
HELP
}

has_force_flag() {
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--force" ]]; then
      echo "1"
      return
    fi
  done
  echo "0"
}

generate_service() {
  local name="$1"
  local force="$2"
  local title
  local base

  require_valid_slug "${name}" "Service name"
  title="$(title_from_slug "${name}")"
  base="${AION_ROOT}/services/${name}"

  write_file "${base}/README.md" "${force}" "$(cat <<DOC
# ${title} Service

## Purpose

Describe the single bounded responsibility of this service.

## Responsibilities

- Define owned business capabilities.
- Own its internal data model.
- Expose versioned APIs and events.
- Emit audit and observability data.
- Enforce authorization and validation.

## Non-Responsibilities

Document capabilities explicitly excluded from this service.

## Interfaces

- REST or internal API
- Events produced
- Events consumed
- Background jobs

## Data Ownership

Document tables, object storage prefixes and retention requirements.

## Security

- Least privilege
- Input validation
- Secret isolation
- Audit logging
- Rate limiting where applicable

## Reliability

- Idempotent commands
- Retry policy
- Dead-letter behavior
- Health checks
- Metrics and alerts

## Testing

- Unit tests
- Contract tests
- Integration tests
- Failure-mode tests
DOC
)"

  write_file "${base}/API.md" "${force}" "$(cat <<DOC
# ${title} API

## Status

Draft

## Conventions

- Version all public contracts.
- Require correlation IDs.
- Support idempotency for mutating operations.
- Return structured error responses.
- Never expose provider secrets.

## Endpoints

Define endpoints only after requirements are approved.
DOC
)"

  write_file "${base}/EVENTS.md" "${force}" "$(cat <<DOC
# ${title} Events

## Event Requirements

Each event must define:

- event name;
- schema version;
- producer;
- consumers;
- idempotency key;
- correlation ID;
- timestamp;
- retry behavior;
- retention policy.
DOC
)"

  write_file "${base}/CONFIG.md" "${force}" "$(cat <<DOC
# ${title} Configuration

## Rules

- Configuration must be environment-driven.
- Secrets must not be committed.
- Defaults must be safe for local development.
- Production values must be validated at startup.
DOC
)"

  write_file "${base}/TESTING.md" "${force}" "$(cat <<DOC
# ${title} Testing

## Required Coverage

- domain rules;
- authorization;
- validation;
- idempotency;
- retry behavior;
- provider failures;
- audit events;
- observability.
DOC
)"

  mkdir -p "${base}/src" "${base}/tests"
  [[ -e "${base}/src/.gitkeep" ]] || : > "${base}/src/.gitkeep"
  [[ -e "${base}/tests/.gitkeep" ]] || : > "${base}/tests/.gitkeep"

  info "Service '${name}' generated successfully."
}

generate_adr() {
  local slug="$1"
  local force="$2"
  local number
  local title
  local path

  require_valid_slug "${slug}" "ADR slug"
  number="$(next_adr_number)"
  title="$(title_from_slug "${slug}")"
  path="${AION_ROOT}/architecture/adrs/ADR-${number}-${slug}.md"

  write_file "${path}" "${force}" "$(cat <<DOC
# ADR-${number}: ${title}

## Status

Proposed

## Date

$(date '+%Y-%m-%d')

## Context

Describe the problem, constraints, assumptions and forces affecting the decision.

## Decision

Describe the chosen approach precisely.

## Alternatives Considered

1. Alternative A
2. Alternative B
3. Do nothing

## Consequences

### Positive

- Describe expected benefits.

### Negative

- Describe costs and trade-offs.

### Risks

- Describe implementation and operational risks.

## Compliance and Security Impact

Describe implications for platform policy, privacy, security and auditability.

## Validation

Define how the decision will be tested or reviewed.

## Revisit Conditions

State what evidence or conditions should trigger reconsideration.
DOC
)"

  info "ADR-${number} generated successfully."
}

generate_workflow() {
  local name="$1"
  local force="$2"
  local title
  local path

  require_valid_slug "${name}" "Workflow name"
  title="$(title_from_slug "${name}")"
  path="${AION_ROOT}/workflows/definitions/${name}.md"

  write_file "${path}" "${force}" "$(cat <<DOC
# ${title} Workflow

## Objective

Define the measurable outcome of this workflow.

## Trigger

Describe manual, scheduled or event-based triggers.

## Preconditions

- Required project state
- Required approvals
- Required credentials
- Required input assets
- Budget and quota checks

## Inputs

| Input | Type | Required | Description |
|---|---|---:|---|
| project_id | UUID | Yes | Owning project |
| correlation_id | UUID | Yes | End-to-end trace identifier |

## Steps

1. Validate inputs.
2. Resolve configuration.
3. Execute domain action.
4. Validate output.
5. Persist provenance.
6. Request human approval when required.
7. Emit events.
8. Record cost and audit information.

## State Model

- Draft
- Queued
- Running
- Awaiting Approval
- Approved
- Rejected
- Failed
- Completed
- Cancelled

## Failure Handling

- Retry only transient failures.
- Use bounded exponential backoff.
- Preserve partial outputs for diagnosis.
- Send terminal failures to a dead-letter mechanism.
- Never publish after an ambiguous failure.

## Idempotency

Define the idempotency key and duplicate-execution behavior.

## Observability

- structured logs;
- workflow duration;
- step duration;
- retry count;
- provider cost;
- failure reason;
- approval latency.

## Security and Compliance

- No fake engagement.
- No unsupported medical claims.
- No public publication without approval.
- Preserve content provenance.
DOC
)"

  info "Workflow '${name}' generated successfully."
}

generate_doc() {
  local section="$1"
  local name="$2"
  local force="$3"
  local title
  local path

  require_valid_slug "${section}" "Documentation section"
  require_valid_slug "${name}" "Document name"

  title="$(title_from_slug "${name}")"
  path="${AION_ROOT}/docs/${section}/${name}.md"

  write_file "${path}" "${force}" "$(cat <<DOC
# ${title}

## Purpose

Define why this document exists and which decisions or requirements it governs.

## Scope

### In Scope

- Add applicable scope.

### Out of Scope

- Add explicit exclusions.

## Context

Describe relevant product, business, technical and compliance context.

## Requirements

Use stable requirement identifiers where applicable.

## Design

Describe the proposed design, interfaces and responsibilities.

## Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| TBD | TBD | TBD | TBD |

## Acceptance Criteria

- Define objective and testable completion criteria.

## Open Questions

- Record unresolved questions.

## References

- Link related ADRs, RFCs, requirements and tests.
DOC
)"

  info "Document '${section}/${name}.md' generated successfully."
}

doctor() {
  local failed="0"
  local path

  for path in \
    "${AION_ROOT}/docs" \
    "${AION_ROOT}/services" \
    "${AION_ROOT}/tools" \
    "${AION_ROOT}/architecture" \
    "${AION_ROOT}/workflows"; do
    if [[ ! -d "${path}" ]]; then
      echo "MISSING: ${path#${AION_ROOT}/}"
      failed="1"
    else
      echo "OK: ${path#${AION_ROOT}/}"
    fi
  done

  if [[ "${failed}" == "1" ]]; then
    exit 1
  fi

  echo "Repository structure is valid."
}

COMMAND="${1:-help}"

case "${COMMAND}" in
  help|-h|--help)
    print_help
    ;;
  version)
    echo "AION CLI v0.2.0"
    ;;
  doctor)
    doctor
    ;;
  generate)
    TYPE="${2:-}"
    FORCE="$(has_force_flag "$@")"

    case "${TYPE}" in
      service)
        [[ -n "${3:-}" ]] || die "Missing service name."
        generate_service "$3" "${FORCE}"
        ;;
      adr)
        [[ -n "${3:-}" ]] || die "Missing ADR slug."
        generate_adr "$3" "${FORCE}"
        ;;
      workflow)
        [[ -n "${3:-}" ]] || die "Missing workflow name."
        generate_workflow "$3" "${FORCE}"
        ;;
      doc)
        [[ -n "${3:-}" ]] || die "Missing documentation section."
        [[ -n "${4:-}" ]] || die "Missing document name."
        generate_doc "$3" "$4" "${FORCE}"
        ;;
      *)
        die "Unknown generator type: ${TYPE:-<empty>}"
        ;;
    esac
    ;;
  *)
    die "Unknown command: ${COMMAND}"
    ;;
esac
EOF

chmod +x "${TARGET}/tools/aion/aion"
chmod +x "${TARGET}/tools/aion/lib/common.sh"

cat > "${TARGET}/tools/README.md" <<'EOF'
# AION Tools

## CLI

The AION CLI generates consistent repository artifacts.

```bash
./tools/aion/aion help
./tools/aion/aion version
./tools/aion/aion doctor
```

## Generators

```bash
./tools/aion/aion generate service audio-engine
./tools/aion/aion generate adr use-postgresql
./tools/aion/aion generate workflow publish-youtube
./tools/aion/aion generate doc architecture storage-strategy
```

## Safety

Generators refuse to overwrite existing files.

Use `--force` only after reviewing the existing artifact:

```bash
./tools/aion/aion generate workflow publish-youtube --force
```

## Naming

Names must use lowercase letters, numbers and single hyphens.
EOF

cat > "${TARGET}/docs/11-operations/aion-cli.md" <<'EOF'
# AION CLI Operations Guide

## Purpose

The CLI standardizes creation of services, ADRs, workflows and documentation.

## Repository Detection

The CLI resolves the repository root relative to its own installation under `tools/aion`.

## Overwrite Protection

Existing generated files are protected by default. The `--force` flag is an explicit destructive override.

## Supported Commands

- `help`
- `version`
- `doctor`
- `generate service`
- `generate adr`
- `generate workflow`
- `generate doc`

## Validation

Run:

```bash
./tools/aion/aion doctor
```

after repository updates and before committing generated artifacts.
EOF

echo "Update 004 applied successfully."
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  ./tools/aion/aion doctor"
echo "  ./tools/aion/aion help"
