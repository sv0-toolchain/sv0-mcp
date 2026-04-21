"""CLI entry point for sv0-mcp using Click."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)


def _resolve_toolchain_root(explicit: str | None) -> Path | None:
    """Resolve the sv0-toolchain root directory.

    Walks up from CWD looking for a directory containing both ``sv0doc/``
    and ``sv0c/`` subdirectories. Returns the explicit path if provided.

    Args:
        explicit: User-provided toolchain root path, or ``None`` for auto-detection.

    Returns:
        Resolved path to the toolchain root, or ``None`` on failure.
    """
    if explicit is not None:
        return Path(explicit).resolve()

    candidate = Path.cwd().resolve()
    for _ in range(10):
        if (candidate / "sv0doc").is_dir() and (candidate / "sv0c").is_dir():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _require_root(ctx: click.Context) -> Path:
    """Extract and validate the toolchain root from the Click context.

    Args:
        ctx: Click context with ``toolchain_root`` in ``ctx.obj``.

    Returns:
        The resolved toolchain root path.

    Raises:
        click.UsageError: If the toolchain root is not configured.
    """
    root: Path | None = ctx.obj.get("toolchain_root")
    if root is None:
        msg = (
            "Cannot determine sv0-toolchain root. "
            "Use --toolchain-root or run from within the toolchain directory."
        )
        raise click.UsageError(msg)
    return root


def _make_client(root: Path) -> tuple:
    """Create settings and graph client from a toolchain root.

    Args:
        root: Resolved toolchain root path.

    Returns:
        Tuple of ``(settings, client)``.
    """
    from sv0_mcp.config import Sv0McpSettings  # noqa: PLC0415
    from sv0_mcp.graph.client import GraphClient  # noqa: PLC0415

    settings = Sv0McpSettings(toolchain_root=root)
    client = GraphClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    return settings, client


@click.group()
@click.option(
    "--toolchain-root",
    type=click.Path(exists=True),
    default=None,
    help="Path to sv0-toolchain root. Auto-detected if not specified.",
)
@click.pass_context
def main(ctx: click.Context, toolchain_root: str | None) -> None:
    """sv0-mcp: Graph memory and MCP server for the sv0 toolchain."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["toolchain_root"] = _resolve_toolchain_root(toolchain_root)


@main.command()
@click.option(
    "--scope",
    type=click.Choice(["all", "spec", "compiler", "vm", "tasks", "structure"]),
    default="all",
    help="Scope of sync operation.",
)
@click.pass_context
def sync(ctx: click.Context, scope: str) -> None:
    """Synchronize the knowledge graph with the sv0-toolchain source."""
    root = _require_root(ctx)
    try:
        from sv0_mcp.graph.sync import GraphSyncEngine, SyncScope  # noqa: PLC0415

        settings, client = _make_client(root)
        try:
            engine = GraphSyncEngine(client=client, settings=settings)
            result = engine.sync(SyncScope(scope))
            console.print(
                f"[green]Sync completed (scope: {result.scope.value})[/green]"
            )
            console.print(f"  Entities created:  {result.entities_created}")
            console.print(f"  Entities updated:  {result.entities_updated}")
            console.print(f"  Relationships:     {result.relationships_created}")
            console.print(f"  Duration:          {result.duration_seconds:.2f}s")
            if result.errors:
                for err in result.errors:
                    console.print(f"  [red]Error: {err}[/red]")
        finally:
            client.close()
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show graph status: entity counts by type."""
    root = _require_root(ctx)
    try:
        _settings, client = _make_client(root)
        try:
            results = client.execute_read(
                "MATCH (e:Entity) "
                "RETURN e.entity_type AS type, count(*) AS count "
                "ORDER BY count DESC"
            )
            table = Table(title="Graph Status")
            table.add_column("Entity Type", style="cyan")
            table.add_column("Count", style="green", justify="right")
            total = 0
            for row in results:
                table.add_row(str(row["type"]), str(row["count"]))
                total += row["count"]
            table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
            console.print(table)
        finally:
            client.close()
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command()
@click.pass_context
def schema(ctx: click.Context) -> None:
    """Apply the graph schema (constraints and indexes)."""
    root = _require_root(ctx)
    try:
        from sv0_mcp.graph.schema import apply_schema  # noqa: PLC0415

        _settings, client = _make_client(root)
        try:
            apply_schema(client)
            console.print("[green]Schema applied successfully.[/green]")
        finally:
            client.close()
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command()
@click.option("--transport", type=click.Choice(["stdio"]), default="stdio")
@click.pass_context
def serve(ctx: click.Context, transport: str) -> None:
    """Start the MCP server."""
    root = _require_root(ctx)
    from sv0_mcp.progress_dashboard_launcher import (  # noqa: PLC0415
        start_with_mcp,
        stop_child,
    )

    dash_proc = start_with_mcp(root)
    if dash_proc is not None:
        port = (
            os.environ.get("SV0_MCP_PROGRESS_DASHBOARD_PORT", "8765").strip() or "8765"
        )
        console.print(
            f"[dim]Progress dashboard (sidecar):[/dim] http://127.0.0.1:{port}/ "
            f"[dim](SV0_MCP_PROGRESS_DASHBOARD=0 to disable)[/dim]"
        )
    try:
        from sv0_mcp.server.mcp import create_server  # noqa: PLC0415

        mcp = create_server()
        console.print(f"[green]Starting MCP server (transport: {transport})...[/green]")
        mcp.run(transport=transport)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)
    finally:
        stop_child(dash_proc)


@main.command()
@click.pass_context
def watch(ctx: click.Context) -> None:
    """Start the file watcher daemon."""
    root = _require_root(ctx)
    try:
        from sv0_mcp.graph.sync import GraphSyncEngine  # noqa: PLC0415
        from sv0_mcp.watchers.file_watcher import FileWatcherDaemon  # noqa: PLC0415

        settings, client = _make_client(root)
        engine = GraphSyncEngine(client=client, settings=settings)
        daemon = FileWatcherDaemon(settings=settings, sync_engine=engine)
        console.print("[green]Starting file watcher...[/green]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]")
        daemon.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Watcher stopped.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command(name="install-hooks")
@click.pass_context
def install_hooks_cmd(ctx: click.Context) -> None:
    """Install git post-commit hooks in sv0doc, sv0c, sv0vm."""
    root = _require_root(ctx)
    try:
        from sv0_mcp.watchers.git_hooks import install_hooks  # noqa: PLC0415

        sv0_mcp_dir = root / "sv0-mcp"
        installed = install_hooks(root, sv0_mcp_dir)
        if installed:
            for path in installed:
                console.print(f"  [green]Installed:[/green] {path}")
        else:
            console.print(
                "[yellow]No hooks installed (repos may lack .git dirs).[/yellow]"
            )
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command(name="uninstall-hooks")
@click.pass_context
def uninstall_hooks_cmd(ctx: click.Context) -> None:
    """Remove git post-commit hooks."""
    root = _require_root(ctx)
    try:
        from sv0_mcp.watchers.git_hooks import uninstall_hooks  # noqa: PLC0415

        removed = uninstall_hooks(root)
        if removed:
            for path in removed:
                console.print(f"  [yellow]Removed:[/yellow] {path}")
        else:
            console.print("[dim]No sv0-mcp hooks found to remove.[/dim]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command()
@click.argument("query")
@click.pass_context
def search(ctx: click.Context, query: str) -> None:
    """Search the graph for entities matching a query."""
    root = _require_root(ctx)
    try:
        _settings, client = _make_client(root)
        try:
            results = client.search_entities(query)
            if not results:
                console.print(f"[yellow]No entities found for: {query}[/yellow]")
                return
            table = Table(title=f"Search Results: {query}")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="magenta")
            for entity in results:
                table.add_row(
                    str(entity.get("name", "")),
                    str(entity.get("entity_type", "")),
                )
            console.print(table)
        finally:
            client.close()
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)


@main.command()
@click.argument("entity_name")
@click.option("--depth", default=1, help="Relationship traversal depth.")
@click.pass_context
def inspect(ctx: click.Context, entity_name: str, depth: int) -> None:  # noqa: ARG001
    """Inspect an entity and its relationships."""
    root = _require_root(ctx)
    try:
        _settings, client = _make_client(root)
        try:
            entity = client.get_entity(entity_name)
            if entity is None:
                console.print(f"[yellow]Entity not found: {entity_name}[/yellow]")
                return

            console.print(f"\n[bold cyan]{entity.get('name', entity_name)}[/bold cyan]")
            console.print(
                f"  Type: [magenta]{entity.get('entity_type', 'unknown')}[/magenta]"
            )
            obs = entity.get("observations", [])
            if obs:
                console.print("  Observations:")
                for o in obs:
                    console.print(f"    - {o}")

            rels = client.get_relationships(entity_name)
            if rels:
                table = Table(title="Relationships")
                table.add_column("Direction", style="dim")
                table.add_column("Type", style="yellow")
                table.add_column("Other", style="cyan")
                for rel in rels:
                    table.add_row(
                        str(rel.get("direction", "")),
                        str(rel.get("relation_type", "")),
                        str(
                            rel.get(
                                "other_name", rel.get("target", rel.get("source", ""))
                            )
                        ),
                    )
                console.print(table)
        finally:
            client.close()
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        ctx.exit(1)
