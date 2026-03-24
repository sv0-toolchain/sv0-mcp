#!/usr/bin/env bash
# Agent-triggered graph sync — called after .Rmd task execution
# Usage: ./scripts/agent-sync.sh <task-key> [status]
set -euo pipefail

TASK_KEY="${1:?Usage: agent-sync.sh <task-key> [status]}"
STATUS="${2:-in_progress}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "Syncing graph after task: $TASK_KEY (status: $STATUS)..."
uv run sv0-mcp sync --scope tasks
uv run sv0-mcp sync --scope structure
