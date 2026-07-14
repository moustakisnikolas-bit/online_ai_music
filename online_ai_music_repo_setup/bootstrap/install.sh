#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "${SCRIPT_DIR}"/*.sh "${SCRIPT_DIR}"/lib/*.sh
echo "Scripts are executable."
echo "Run: ./00-bootstrap-aion.sh"
