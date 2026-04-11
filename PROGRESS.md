# sv0-mcp — progress (submodule)

**Meta-repo rollup:** when this tree is the `sv0-mcp/` submodule of **sv0-toolchain**, the parent copies this file’s **`%`** into `task/sv0-toolchain-progress.md`. **Standalone clone:** keep this file authoritative here; reconcile on the next meta-repo integration.

**Last updated:** 2026-04-10

## Checklist (local source of truth)

| ID | Item | Done (0/1) |
|----|------|------------|
| MCP-1 | Server + docs match `task/sv0-mcp-milestone-0.Rmd` completion story | 1 |
| MCP-2 | Graph sync discipline documented; sync after task/spec layout changes per parent rules | 1 |
| MCP-3 | Tests / CI for MCP project green when toolchain tasks change graph inputs | 1 |

## Completion

- **Done:** count rows with `Done = 1` above.
- **Total:** row count of the checklist.
- **%:** `Done / Total * 100`.

## Notes

- 2026-04-10: Reconciled with `task/sv0-mcp-milestone-0.Rmd` (`state: complete`). Server, tests, docs, sync discipline, `sv0doc` hub mention, parent workspace references — all documented. Graph sync runs after `task/` or normative `sv0doc/` layout changes per parent rules (`32-sv0-mcp-tooling-boundaries.mdc`).
- MCP-3: `./scripts/sv0 test-guards` includes milestone-orientation + workspace-table consistency; MCP-specific tests via `./scripts/sv0 test-mcp` when applicable.
