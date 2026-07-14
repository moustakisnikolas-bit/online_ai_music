#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

write_file_if_missing "${AION_ROOT}/docker-compose.yml" "$(cat <<'EOF'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: aion
      POSTGRES_PASSWORD: aion
      POSTGRES_DB: aion
    ports:
      - "5432:5432"
    volumes:
      - aion-postgres:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: aion
      MINIO_ROOT_PASSWORD: change-me-now
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - aion-minio:/data

volumes:
  aion-postgres:
  aion-minio:
EOF
)"

write_file_if_missing "${AION_ROOT}/Makefile" "$(cat <<'EOF'
.PHONY: help bootstrap validate infra-up infra-down

help:
	@echo "AION commands"
	@echo "  make validate"
	@echo "  make infra-up"
	@echo "  make infra-down"

validate:
	@bash scripts/validate.sh

infra-up:
	docker compose up -d

infra-down:
	docker compose down
EOF
)"

write_file_if_missing "${AION_ROOT}/scripts/validate.sh" "$(cat <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

required=(
  README.md
  AGENTS.md
  docs/01-product/prd.md
  docs/03-requirements/srs.md
  docs/04-architecture/architecture.md
  architecture/adrs/ADR-0001-modular-monolith-first.md
)

for path in "${required[@]}"; do
  [[ -f "${path}" ]] || { echo "Missing: ${path}" >&2; exit 1; }
done

echo "Repository baseline is valid."
EOF
)"
run_cmd chmod +x "${AION_ROOT}/scripts/validate.sh"
