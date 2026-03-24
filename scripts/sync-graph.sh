#!/usr/bin/env bash
# On-demand graph sync for sv0-toolchain
# Usage: ./scripts/sync-graph.sh [scope]
# Scopes: all, spec, compiler, vm, tasks, structure
set -euo pipefail

SCOPE="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "Syncing sv0 graph (scope: $SCOPE)..."
uv run sv0-mcp sync --scope "$SCOPE"
