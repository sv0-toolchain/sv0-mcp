# sv0-mcp — progress

**Live status is tracked in one place:** the parent workspace's
[`task/sv0-toolchain-progress.md`](../task/sv0-toolchain-progress.md). When this
tree is the `sv0-mcp/` submodule of **sv0-toolchain**, that file is authoritative.

## current state

- **Milestone 0 complete** — the Neo4j knowledge graph + MCP servers are in place
  (spec entities, compiler phases, VM components, task/workflow state, and
  traceability links), with auto-sync via file watchers, git hooks, and
  agent-triggered runs. Setup, graph model, tools, and CLI are documented in
  [`README.md`](README.md).
- Full sync: `./scripts/sync-graph.sh all` after `docker compose up -d neo4j`.

_Historical note: the detailed run log lives in git history and the parent
progress rollup; it is not duplicated here to keep a single source of truth._
