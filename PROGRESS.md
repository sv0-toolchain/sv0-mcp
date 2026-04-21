# sv0-mcp — progress (submodule)

**Meta-repo rollup:** when this tree is the `sv0-mcp/` submodule of **sv0-toolchain**, the parent copies this file’s **`%`** into `task/sv0-toolchain-progress.md`. **Standalone clone:** keep this file authoritative here; reconcile on the next meta-repo integration.

**Last updated:** 2026-04-21 (docker compose: **`progress-dashboard`** service + **`docker-compose.yml`** comments; **`README.md`** §1 stack URLs)

## Checklist (local source of truth)

| ID | Item | Done (0/1) |
|----|------|------------|
| MCP-1 | Server + docs match `task/sv0-mcp-milestone-0.Rmd` completion story | 1 |
| MCP-2 | Graph sync discipline documented; sync after task/spec layout changes per parent rules | 1 |
| MCP-3 | Tests / CI for MCP project green when toolchain tasks change graph inputs | 1 |
| MCP-4 | `sv0-mcp serve` spawns meta-repo progress dashboard (opt-out env); **`docker compose up -d`** also starts **`progress-dashboard`** (mount + **8766** host port default); README documents ports, TTL, mount env | 1 |

## Completion

- **Done:** count rows with `Done = 1` above.
- **Total:** row count of the checklist.
- **%:** `Done / Total * 100`.

## Notes

- 2026-04-21: **`docker compose`** — second service **`progress-dashboard`** (`python:3.12-slim`) runs **`scripts/progress_dashboard_server.py`** with **`--host 0.0.0.0`**, bind-mount **`SV0_MCP_TOOLCHAIN_ROOT`** (default **`..`**) at **`/workspace:ro`**, publishes **`8766:8765`** by default (`SV0_MCP_PROGRESS_DASHBOARD_HOST_PORT` / **`SV0_MCP_PROGRESS_DASHBOARD_REFRESH`**).
- 2026-04-21: **`serve`** starts **`scripts/progress_dashboard_server.py`** as a subprocess when **`SV0_MCP_PROGRESS_DASHBOARD`** is unset/truthy; dashboard APIs use an in-process TTL cache (default **120s** refresh) so periodic browser polls stay cheap. **`sv0-mcp/README.md`** lists env vars.
- 2026-04-10: Reconciled with `task/sv0-mcp-milestone-0.Rmd` (`state: complete`). Server, tests, docs, sync discipline, `sv0doc` hub mention, parent workspace references — all documented. Graph sync runs after `task/` or normative `sv0doc/` layout changes per parent rules (`32-sv0-mcp-tooling-boundaries.mdc`).
- MCP-3: `./scripts/sv0 test-guards` includes milestone-orientation + workspace-table consistency; MCP-specific tests via `./scripts/sv0 test-mcp` when applicable.
