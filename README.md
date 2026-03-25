# sv0-mcp

self-updating graph memory and MCP server for the sv0 programming language toolchain.

## purpose

sv0-mcp maintains a Neo4j knowledge graph of the sv0 toolchain — specification entities (grammar productions, type rules, contracts, memory model), compiler architecture (phases, modules), VM components, task/workflow state, and cross-cutting traceability links. the graph updates automatically via file watchers, git hooks, and agent-triggered sync.

two MCP servers provide AI-assisted development:

1. **generic Neo4j Cypher access** — `read_neo4j_cypher`, `write_neo4j_cypher`, `get_neo4j_schema` via the standard `mcp-neo4j-cypher` server, pointed at the dedicated sv0 instance
2. **sv0-specific tools** — domain-aware operations like `get_spec_for_phase`, `trace_rule_to_implementation`, `get_milestone_progress`, `get_compiler_pipeline`

> **note:** the `mcp-neo4j-memory` server is **not compatible** with the sv0 graph schema. it operates on `Memory`-labeled nodes, whereas sv0 uses `Entity` as the base label with typed secondary labels (e.g. `GrammarProduction`, `CompilerPhase`). use the `sv0-graph` server's `search_spec` and `get_entity_graph` tools for discovery, or `sv0-neo4j-cypher` for ad-hoc queries.

## setup

### 1. start the neo4j instance

```bash
cd sv0-mcp
docker compose up -d
```

the sv0 graph runs on non-default ports to avoid conflicts:

- HTTP browser: `http://localhost:7475`
- bolt: `bolt://localhost:7688`
- credentials: `neo4j` / `sv0-graph-dev`

### 2. install dependencies

```bash
cd sv0-mcp
uv sync
```

### 3. initial sync

```bash
uv run sv0-mcp sync
```

### 4. start the MCP server

```bash
uv run sv0-mcp serve
```

## cursor MCP configuration

add the following to your cursor MCP settings to connect both the generic and custom servers.

### generic neo4j cypher access (sv0 instance)

```json
{
  "sv0-neo4j-cypher": {
    "command": "uvx",
    "args": ["mcp-neo4j-cypher"],
    "env": {
      "NEO4J_URI": "bolt://localhost:7688",
      "NEO4J_USERNAME": "neo4j",
      "NEO4J_PASSWORD": "sv0-graph-dev"
    }
  }
}
```

### custom sv0 graph server

```json
{
  "sv0-graph": {
    "command": "uv",
    "args": ["--directory", "/path/to/sv0-toolchain/sv0-mcp", "run", "sv0-mcp", "serve"],
    "env": {
      "SV0_MCP_TOOLCHAIN_ROOT": "/path/to/sv0-toolchain"
    }
  }
}
```

## cli commands

| command | description |
|---|---|
| `sv0-mcp sync [--scope SCOPE]` | sync the graph (scopes: all, spec, compiler, vm, tasks, structure) |
| `sv0-mcp status` | show entity counts by type |
| `sv0-mcp schema` | apply graph constraints and indexes |
| `sv0-mcp serve` | start the custom MCP server |
| `sv0-mcp watch` | start the file watcher daemon |
| `sv0-mcp install-hooks` | install git post-commit hooks |
| `sv0-mcp uninstall-hooks` | remove git post-commit hooks |
| `sv0-mcp search QUERY` | search for entities by name/content |
| `sv0-mcp inspect ENTITY [--depth N]` | inspect an entity and its relationships |

## update mechanisms

| mechanism | trigger | scope |
|---|---|---|
| **git hooks** | post-commit in sv0doc/sv0c/sv0vm | auto-detected per repo |
| **file watcher** | file create/modify/delete | debounced, scope-aware |
| **agent-triggered** | after .Rmd task execution | tasks + structure |
| **on-demand** | `sv0-mcp sync` or MCP `sync_graph` tool | configurable scope |

## graph data model

### entity types

| category | entity types |
|---|---|
| specification (sv0doc) | GrammarProduction, TypeRule, ContractRule, MemoryRule, Keyword, Operator, PrimitiveType, TraitSpec, DesignDecision |
| compiler (sv0c) | CompilerPhase, CompilerModule, AstNode, IrConstruct |
| vm (sv0vm) | VmComponent, VmModule |
| workflow | Task, Milestone, Roadmap |
| structure | SourceFile, Directory, Subproject |

task ``.Rmd`` YAML: optional ``graph_entity_type`` (`task` \| `milestone` \| `roadmap`) overrides the default milestone heuristic; ``roadmap_parent`` links a node to a Roadmap via ``PART_OF``. the task extractor normalizes a missing space after ``:`` for known keys (e.g. ``state:done`` → ``state: done``) and skips any file that still fails to parse, logging an error instead of aborting the whole sync.

### relationship types

| relationship | meaning |
|---|---|
| DEFINES | source file defines an entity |
| IMPLEMENTS | module implements a spec rule |
| DEPENDS_ON | entity depends on another |
| CONTAINS | directory/milestone contains children |
| PRODUCES | phase produces output |
| CONSUMES | phase consumes input |
| SPECIFIES | spec entity specifies a compiler phase |
| REFERENCES | entity references another (e.g. grammar cross-references) |
| PART_OF | entity belongs to a subproject, or a task/milestone belongs to a **Roadmap** (`roadmap_parent` in task YAML) |
| PRECEDES | ordering between phases/components |
| TRACES_TO | traceability link from spec to implementation |
| INCLUDES | milestone includes task |
| CHILD_OF | parent-child hierarchy |

## custom MCP tools

| tool | description |
|---|---|
| `get_spec_for_phase` | all spec entities relevant to a compiler phase |
| `trace_rule_to_implementation` | find implementations of a spec rule |
| `get_task_status` | task status, title, tags, dependencies |
| `get_milestone_progress` | milestone completion percentage |
| `get_roadmap_children` | milestones/tasks under a Roadmap (`PART_OF`) |
| `get_dependencies` | all dependencies for an entity |
| `get_compiler_pipeline` | full compiler pipeline view |
| `search_spec` | search across spec entities |
| `sync_graph` | trigger manual graph sync |
| `get_design_decisions` | all design decisions with rationale |
| `get_grammar_production` | specific grammar production EBNF |
| `get_entity_graph` | entity with connected entities (depth-configurable) |

## development

```bash
# install dev dependencies
uv sync --all-extras

# run tests
uv run pytest

# lint
uv run ruff check src/ tests/

# format
uv run ruff format src/ tests/
```

## environment variables

| variable | default | description |
|---|---|---|
| `SV0_MCP_NEO4J_URI` | `bolt://localhost:7688` | neo4j bolt uri |
| `SV0_MCP_NEO4J_USER` | `neo4j` | neo4j username |
| `SV0_MCP_NEO4J_PASSWORD` | `sv0-graph-dev` | neo4j password |
| `SV0_MCP_NEO4J_DATABASE` | `neo4j` | neo4j database name |
| `SV0_MCP_TOOLCHAIN_ROOT` | auto-detected | path to sv0-toolchain root |
| `SV0_MCP_WATCH_DEBOUNCE_SECONDS` | `1.0` | file watcher debounce interval |
| `SV0_MCP_LOG_LEVEL` | `INFO` | logging level |

## development tracking

when this repository is checked out as **`sv0-mcp/`** inside the parent **sv0-toolchain** meta-repo:

- workspace index: [`task/sv0-toolchain-workspace.Rmd`](../task/sv0-toolchain-workspace.Rmd)
- MCP milestone tasks: [`task/sv0-mcp-milestone-0.Rmd`](../task/sv0-mcp-milestone-0.Rmd)
- aggregate tests from parent: `./scripts/sv0 test-mcp` or `make -C .. test-mcp`
