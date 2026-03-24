"""Custom MCP server for the sv0 knowledge graph."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from sv0_mcp.config import Sv0McpSettings
from sv0_mcp.graph.client import GraphClient
from sv0_mcp.graph.schema import apply_schema
from sv0_mcp.graph.sync import GraphSyncEngine, SyncScope

logger = logging.getLogger(__name__)

_MAX_GRAPH_DEPTH = 5


def create_server() -> FastMCP:  # noqa: PLR0915
    """Initialize the sv0 graph MCP server.

    Creates settings, a graph client, applies the schema,
    and registers all tools and resources on a new
    :class:`FastMCP` instance.

    Returns:
        Fully configured ``FastMCP`` server.
    """
    settings = Sv0McpSettings()
    client = GraphClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    apply_schema(client)
    engine = GraphSyncEngine(client, settings)

    mcp = FastMCP(
        "sv0-graph",
        instructions=(
            "Knowledge graph server for the "
            "sv0 programming language toolchain"
        ),
    )

    # --------------------------------------------------------------
    # Tools
    # --------------------------------------------------------------

    @mcp.tool()
    def get_spec_for_phase(phase_name: str) -> str:
        """Get all spec entities for a compiler phase.

        Queries the graph for grammar productions, type rules,
        and other spec entities that SPECIFIES or TRACES_TO
        the named compiler phase.

        Args:
            phase_name: Name of the compiler phase
                (e.g. ``lexer``, ``type_checker``).

        Returns:
            Formatted text listing matching spec entities.
        """
        query = (
            "MATCH (spec:Entity)"
            "-[r:SPECIFIES|TRACES_TO]->"
            "(phase:Entity {name: $phase}) "
            "RETURN spec.name AS name, "
            "spec.entity_type AS type, "
            "spec.observations AS observations, "
            "type(r) AS relation"
        )
        try:
            results = client.execute_read(
                query, {"phase": phase_name}
            )
        except Exception as exc:
            return (
                f"Error querying spec for phase "
                f"'{phase_name}': {exc}"
            )
        if not results:
            return (
                "No spec entities found for "
                f"phase '{phase_name}'."
            )
        lines = [
            f"Spec entities for phase "
            f"'{phase_name}':\n",
        ]
        for r in results:
            lines.append(
                f"  [{r.get('type', '?')}] "
                f"{r.get('name', '?')}"
            )
            lines.append(
                f"    Relation: {r.get('relation', '?')}"
            )
            for obs in r.get("observations") or []:
                lines.append(f"    - {obs}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    def trace_rule_to_implementation(
        rule_name: str,
    ) -> str:
        """Trace a spec rule to its implementations.

        Finds all IMPLEMENTS and TRACES_TO relationships
        from spec entities to compiler / VM entities.

        Args:
            rule_name: Name of the spec rule to trace.

        Returns:
            Formatted implementation chain.
        """
        query = (
            "MATCH (impl:Entity)-[:IMPLEMENTS]->"
            "(spec:Entity {name: $name}) "
            "RETURN impl.name AS name, "
            "impl.entity_type AS type "
            "UNION "
            "MATCH (spec:Entity {name: $name})"
            "-[:TRACES_TO]->(impl:Entity) "
            "RETURN impl.name AS name, "
            "impl.entity_type AS type"
        )
        try:
            results = client.execute_read(
                query, {"name": rule_name}
            )
        except Exception as exc:
            return (
                f"Error tracing rule "
                f"'{rule_name}': {exc}"
            )
        if not results:
            return (
                "No implementations found for "
                f"'{rule_name}'."
            )
        lines = [
            f"Implementations of '{rule_name}':\n",
        ]
        for r in results:
            lines.append(
                f"  [{r.get('type', '?')}] "
                f"{r.get('name', '?')}"
            )
        return "\n".join(lines)

    @mcp.tool()
    def get_task_status(task_key: str) -> str:
        """Get a task by key from the graph.

        Returns the task's status, title, tags, and any
        dependent tasks.

        Args:
            task_key: Task identifier key.

        Returns:
            Formatted task status information.
        """
        query = (
            "MATCH (t:Entity {name: $key}) "
            "WHERE t.entity_type = 'Task' "
            "OPTIONAL MATCH (t)-[:DEPENDS_ON]->"
            "(dep:Entity) "
            "RETURN t, "
            "collect(dep.name) AS dependencies"
        )
        try:
            results = client.execute_read(
                query, {"key": task_key}
            )
        except Exception as exc:
            return (
                f"Error fetching task "
                f"'{task_key}': {exc}"
            )
        if not results:
            return f"Task '{task_key}' not found."
        task = results[0]["t"]
        deps = results[0]["dependencies"]
        tags = task.get("tags") or []
        lines = [
            f"Task: {task.get('name', 'unknown')}",
            f"  Title: {task.get('title', 'N/A')}",
            f"  State: {task.get('state', 'unknown')}",
            f"  Tags: {', '.join(tags)}",
        ]
        if deps:
            lines.append("  Dependencies:")
            for dep in deps:
                lines.append(f"    - {dep}")
        return "\n".join(lines)

    @mcp.tool()
    def get_milestone_progress(
        milestone_key: str,
    ) -> str:
        """Get milestone progress with all task statuses.

        Computes a completion percentage from the tasks
        linked via INCLUDES relationships.

        Args:
            milestone_key: Milestone identifier key.

        Returns:
            Formatted milestone progress summary.
        """
        query = (
            "MATCH (m:Entity {name: $key}) "
            "WHERE m.entity_type = 'Milestone' "
            "OPTIONAL MATCH (m)-[:INCLUDES]->"
            "(t:Entity) "
            "WHERE t.entity_type = 'Task' "
            "RETURN m, collect("
            "{name: t.name, state: t.state}"
            ") AS tasks"
        )
        try:
            results = client.execute_read(
                query, {"key": milestone_key}
            )
        except Exception as exc:
            return (
                f"Error fetching milestone "
                f"'{milestone_key}': {exc}"
            )
        if not results:
            return (
                f"Milestone '{milestone_key}' not found."
            )
        milestone = results[0]["m"]
        tasks = results[0]["tasks"]
        total = len(tasks)
        done = sum(
            1
            for t in tasks
            if t.get("state") == "done"
        )
        pct = (done / total * 100) if total else 0
        lines = [
            f"Milestone: "
            f"{milestone.get('name', 'unknown')}",
            f"  Title: "
            f"{milestone.get('title', 'N/A')}",
            f"  Progress: {done}/{total} ({pct:.0f}%)",
            "",
            "  Tasks:",
        ]
        for t in tasks:
            state = t.get("state", "unknown")
            marker = "x" if state == "done" else " "
            lines.append(
                f"    [{marker}] "
                f"{t.get('name', '?')} ({state})"
            )
        return "\n".join(lines)

    @mcp.tool()
    def get_dependencies(entity_name: str) -> str:
        """Get all dependencies for an entity.

        Queries DEPENDS_ON, CONSUMES, and REFERENCES
        relationships.

        Args:
            entity_name: Name of the entity.

        Returns:
            Formatted dependency list.
        """
        query = (
            "MATCH (e:Entity {name: $name})"
            "-[r:DEPENDS_ON|CONSUMES|REFERENCES]->"
            "(dep:Entity) "
            "RETURN type(r) AS relation, "
            "dep.name AS name, "
            "dep.entity_type AS type"
        )
        try:
            results = client.execute_read(
                query, {"name": entity_name}
            )
        except Exception as exc:
            return (
                f"Error fetching dependencies for "
                f"'{entity_name}': {exc}"
            )
        if not results:
            return (
                "No dependencies found for "
                f"'{entity_name}'."
            )
        lines = [
            f"Dependencies of '{entity_name}':\n",
        ]
        for r in results:
            lines.append(
                f"  [{r.get('relation', '?')}] "
                f"{r.get('name', '?')} "
                f"({r.get('type', '?')})"
            )
        return "\n".join(lines)

    @mcp.tool()
    def get_compiler_pipeline() -> str:
        """Get the full compiler pipeline.

        Queries all CompilerPhase entities and their
        PRECEDES relationships.  Produces an ordered view
        of the compilation stages.

        Returns:
            Formatted pipeline text.
        """
        query = (
            "MATCH (p:Entity) "
            "WHERE p.entity_type = 'CompilerPhase' "
            "OPTIONAL MATCH (p)-[:PRECEDES]->"
            "(next:Entity) "
            "RETURN p.name AS phase, "
            "p.description AS description, "
            "p.input_type AS input_type, "
            "p.output_type AS output_type, "
            "next.name AS next_phase"
        )
        try:
            results = client.execute_read(query)
        except Exception as exc:
            return f"Error fetching pipeline: {exc}"
        if not results:
            return (
                "No compiler phases found in the graph."
            )
        successors: dict[str, str] = {}
        phases: dict[str, dict[str, str | None]] = {}
        for r in results:
            name = r["phase"]
            phases[name] = r
            if r.get("next_phase"):
                successors[name] = r["next_phase"]
        all_targets = set(successors.values())
        starts = [
            p for p in phases if p not in all_targets
        ]
        current: str | None = (
            starts[0] if starts else next(iter(phases))
        )
        ordered: list[str] = []
        while current and current not in ordered:
            ordered.append(current)
            current = successors.get(current)
        lines = ["sv0 Compiler Pipeline:\n"]
        for i, name in enumerate(ordered):
            p = phases.get(name, {})
            lines.append(f"  {i + 1}. {name}")
            if p.get("description"):
                lines.append(
                    f"     {p['description']}"
                )
            if p.get("input_type"):
                lines.append(
                    f"     Input:  {p['input_type']}"
                )
            if p.get("output_type"):
                lines.append(
                    f"     Output: {p['output_type']}"
                )
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    def search_spec(query: str) -> str:
        """Search across all spec entities.

        Searches grammar productions, type rules, contract
        rules, memory rules, keywords, and operators by
        name and observations.

        Args:
            query: Substring to search for.

        Returns:
            Formatted search results.
        """
        spec_types = [
            "GrammarProduction",
            "TypeRule",
            "ContractRule",
            "MemoryRule",
            "Keyword",
            "Operator",
        ]
        cypher = (
            "MATCH (e:Entity) "
            "WHERE e.entity_type IN $types "
            "AND (e.name CONTAINS $query "
            "OR ANY(obs IN e.observations "
            "WHERE obs CONTAINS $query)) "
            "RETURN e.name AS name, "
            "e.entity_type AS type, "
            "e.observations AS observations "
            "LIMIT 20"
        )
        try:
            results = client.execute_read(
                cypher,
                {"types": spec_types, "query": query},
            )
        except Exception as exc:
            return f"Error searching spec: {exc}"
        if not results:
            return (
                "No spec entities match "
                f"'{query}'."
            )
        lines = [
            f"Spec search results for '{query}':\n",
        ]
        for r in results:
            lines.append(
                f"  [{r.get('type', '?')}] "
                f"{r.get('name', '?')}"
            )
            for obs in (r.get("observations") or [])[:3]:
                lines.append(f"    - {obs}")
        return "\n".join(lines)

    @mcp.tool()
    def sync_graph(scope: str = "all") -> str:
        """Trigger a graph sync for the given scope.

        Runs the appropriate extractors and merges
        entities / relationships into the graph.

        Args:
            scope: One of ``all``, ``spec``, ``compiler``,
                ``vm``, ``tasks``, ``structure``.

        Returns:
            Formatted sync result summary.
        """
        try:
            sync_scope = SyncScope(scope)
        except ValueError:
            valid = ", ".join(s.value for s in SyncScope)
            return (
                f"Invalid scope '{scope}'. "
                f"Valid scopes: {valid}"
            )
        result = engine.sync(sync_scope)
        lines = [
            "Sync complete "
            f"(scope: {result.scope.value}):",
            f"  Entities created:  "
            f"{result.entities_created}",
            f"  Entities updated:  "
            f"{result.entities_updated}",
            f"  Relationships:     "
            f"{result.relationships_created}",
            f"  Duration:          "
            f"{result.duration_seconds:.2f}s",
        ]
        if result.errors:
            lines.append(
                f"\n  Errors ({len(result.errors)}):"
            )
            for err in result.errors:
                lines.append(f"    - {err}")
        return "\n".join(lines)

    @mcp.tool()
    def get_design_decisions() -> str:
        """Get all DesignDecision entities.

        Returns formatted design decisions with their
        summaries and rationale.

        Returns:
            Formatted list of design decisions.
        """
        try:
            results = client.execute_read(
                "MATCH (d:Entity) "
                "WHERE d.entity_type = 'DesignDecision' "
                "RETURN d ORDER BY d.name",
            )
        except Exception as exc:
            return (
                f"Error fetching design decisions: {exc}"
            )
        if not results:
            return "No design decisions found."
        lines = ["Design Decisions:\n"]
        for r in results:
            d = r["d"]
            lines.append(f"  {d.get('name', '?')}:")
            if d.get("summary"):
                lines.append(
                    f"    Summary: {d['summary']}"
                )
            if d.get("rationale"):
                lines.append(
                    f"    Rationale: {d['rationale']}"
                )
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    def get_grammar_production(name: str) -> str:
        """Get a specific grammar production by name.

        Returns the production's EBNF definition, section,
        and any associated observations.

        Args:
            name: Production name.

        Returns:
            Formatted production details.
        """
        query = (
            "MATCH (g:Entity {name: $name}) "
            "WHERE g.entity_type = 'GrammarProduction' "
            "RETURN g"
        )
        try:
            results = client.execute_read(
                query, {"name": name}
            )
        except Exception as exc:
            return (
                f"Error fetching production "
                f"'{name}': {exc}"
            )
        if not results:
            return (
                f"Grammar production '{name}' not found."
            )
        g = results[0]["g"]
        lines = [
            f"Grammar Production: "
            f"{g.get('name', '?')}",
            f"  Section: {g.get('section', 'N/A')}",
        ]
        if g.get("definition"):
            lines.append(
                f"\n  Definition:\n    "
                f"{g['definition']}"
            )
        if g.get("observations"):
            lines.append("\n  Notes:")
            for obs in g["observations"]:
                lines.append(f"    - {obs}")
        return "\n".join(lines)

    @mcp.tool()
    def get_entity_graph(
        entity_name: str,
        depth: int = 1,
    ) -> str:
        """Get an entity and connected entities.

        Traverses the graph up to *depth* hops from the
        named entity and returns all connected nodes.

        Args:
            entity_name: Center entity name.
            depth: Maximum traversal depth (1-5).

        Returns:
            Formatted subgraph text.
        """
        clamped = min(max(depth, 1), _MAX_GRAPH_DEPTH)
        try:
            center = client.get_entity(entity_name)
        except Exception as exc:
            return (
                f"Error fetching entity "
                f"'{entity_name}': {exc}"
            )
        if not center:
            return f"Entity '{entity_name}' not found."
        query = (
            f"MATCH (e:Entity {{name: $name}})"
            f"-[r*1..{clamped}]-(c:Entity) "
            "RETURN DISTINCT c.name AS name, "
            "c.entity_type AS type, "
            "[rel IN r | type(rel)] AS relations "
            "LIMIT 50"
        )
        try:
            connected = client.execute_read(
                query, {"name": entity_name}
            )
        except Exception as exc:
            return (
                f"Error traversing graph from "
                f"'{entity_name}': {exc}"
            )
        etype = center.get("entity_type", "?")
        lines = [
            f"Entity: {center.get('name')} [{etype}]",
        ]
        for obs in center.get("observations") or []:
            lines.append(f"  - {obs}")
        if connected:
            lines.append(
                f"\nConnected ({len(connected)}):"
            )
            for c in connected:
                rels = " -> ".join(
                    c.get("relations") or []
                )
                lines.append(
                    f"  [{c.get('type', '?')}] "
                    f"{c.get('name', '?')} ({rels})"
                )
        return "\n".join(lines)

    # --------------------------------------------------------------
    # Resources
    # --------------------------------------------------------------

    @mcp.resource("sv0://schema")
    def get_schema_resource() -> str:
        """Current graph schema with node type and relationship type counts."""
        try:
            label_results = client.execute_read(
                "MATCH (n:Entity) "
                "RETURN n.entity_type AS type, "
                "count(*) AS count "
                "ORDER BY count DESC",
            )
            rel_results = client.execute_read(
                "MATCH ()-[r]->() "
                "RETURN type(r) AS type, "
                "count(*) AS count "
                "ORDER BY count DESC",
            )
        except Exception as exc:
            return f"Error reading schema: {exc}"
        lines = ["Graph Schema\n", "Node Types:"]
        for r in label_results:
            lines.append(
                f"  {r['type']}: {r['count']}"
            )
        lines.append("\nRelationship Types:")
        for r in rel_results:
            lines.append(
                f"  {r['type']}: {r['count']}"
            )
        return "\n".join(lines)

    @mcp.resource("sv0://pipeline")
    def get_pipeline_resource() -> str:
        """Compiler pipeline view."""
        return get_compiler_pipeline()

    @mcp.resource("sv0://milestones")
    def get_milestones_resource() -> str:
        """All milestones and their progress."""
        query = (
            "MATCH (m:Entity) "
            "WHERE m.entity_type = 'Milestone' "
            "OPTIONAL MATCH (m)-[:INCLUDES]->"
            "(t:Entity) "
            "WHERE t.entity_type = 'Task' "
            "RETURN m.name AS milestone, "
            "m.title AS title, "
            "collect({name: t.name, "
            "state: t.state}) AS tasks"
        )
        try:
            results = client.execute_read(query)
        except Exception as exc:
            return (
                f"Error reading milestones: {exc}"
            )
        if not results:
            return "No milestones found."
        lines = ["Milestones:\n"]
        for r in results:
            tasks = r["tasks"]
            total = len(tasks)
            done = sum(
                1
                for t in tasks
                if t.get("state") == "done"
            )
            pct = (done / total * 100) if total else 0
            lines.append(
                f"  {r['milestone']}: "
                f"{r.get('title', 'N/A')}"
            )
            lines.append(
                f"    Progress: "
                f"{done}/{total} ({pct:.0f}%)"
            )
        return "\n".join(lines)

    return mcp
