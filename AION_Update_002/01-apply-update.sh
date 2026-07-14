#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-$(pwd)}"

mkdir -p "$TARGET/docs/04-architecture"
mkdir -p "$TARGET/docs/05-ai"
mkdir -p "$TARGET/docs/06-factories"

cat > "$TARGET/docs/04-architecture/domain-model.md" <<'EOF'
# Domain Model

## Core Domains

- Identity
- Projects
- Brands
- Assets
- Audio Generation
- Image Generation
- Video Generation
- Metadata
- Review
- Publishing
- Analytics
- AI Routing

## Aggregate Roots

- Project
- Asset
- Workflow
- Publication
- Brand
EOF

cat > "$TARGET/docs/05-ai/ai-employees.md" <<'EOF'
# AI Employees

## Executive Layer
- CEO Agent
- Product Manager
- Architect

## Production Layer
- Audio Producer
- Artwork Producer
- Video Producer
- Metadata Writer

## Operations Layer
- Publisher
- QA Reviewer
- Analytics Analyst
EOF

cat > "$TARGET/docs/06-factories/ambient-factory.md" <<'EOF'
# Ambient Factory

## Inputs
- Theme
- Duration
- Mood
- Language
- Target Platforms

## Outputs
- WAV
- FLAC
- MP3
- Artwork
- Video
- Metadata
- Publishing Package
EOF

echo "Update 002 applied successfully."
