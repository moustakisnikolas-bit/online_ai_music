#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "${SCRIPT_DIR}"/*.sh
chmod +x "${SCRIPT_DIR}"/bootstrap/*.sh
chmod +x "${SCRIPT_DIR}"/bootstrap/lib/*.sh
echo "Executable permissions applied."
