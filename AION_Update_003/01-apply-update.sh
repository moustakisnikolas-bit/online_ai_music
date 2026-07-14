#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

mkdir -p "$TARGET/tools/aion"
mkdir -p "$TARGET/tools/templates"
mkdir -p "$TARGET/tools/internal"

cat > "$TARGET/tools/aion/aion" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

COMMAND="${1:-help}"

case "$COMMAND" in
  help)
    cat <<EOT
AION CLI

Commands

  help
  version
  doctor
  generate
EOT
  ;;

  version)
    echo "AION CLI v0.1.0"
  ;;

  doctor)
    echo "Checking repository..."

    required=(
      docs
      services
      tools
      architecture
    )

    failed=0

    for d in "${required[@]}"; do
      if [[ ! -d "$d" ]]; then
        echo "Missing: $d"
        failed=1
      fi
    done

    if [[ "$failed" == "0" ]]; then
      echo "Repository OK"
    else
      exit 1
    fi
  ;;

  generate)
    echo "Generator module will be implemented in Update 004."
  ;;

  *)
    echo "Unknown command."
    exit 1
  ;;
esac
EOF

chmod +x "$TARGET/tools/aion/aion"

cat > "$TARGET/tools/README.md" <<'EOF'
# AION Tools

This directory contains the internal development tools.

Planned:

- documentation generator
- service generator
- ADR generator
- API generator
- workflow generator
- AI agent generator
EOF

echo "Update 003 applied successfully."
