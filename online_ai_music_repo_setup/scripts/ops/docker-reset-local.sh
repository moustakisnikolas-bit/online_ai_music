#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

echo "This will stop containers and remove local Docker volumes."
echo "Generated files under data/generated will not be deleted."
echo
read -r -p "Continue? [y/N] " answer

case "${answer}" in
  y|Y|yes|YES)
    docker compose down --volumes --remove-orphans
    echo "Local Docker stack and volumes removed."
    ;;
  *)
    echo "Cancelled."
    ;;
esac
