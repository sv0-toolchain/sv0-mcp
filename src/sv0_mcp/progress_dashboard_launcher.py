"""Start the meta-repo progress dashboard HTTP server alongside ``sv0-mcp serve``.

The dashboard script lives in the parent sv0-toolchain checkout
(``<toolchain_root>/scripts/progress_dashboard_server.py``). When the MCP server
exits, the child process is terminated.

Environment (all optional):

* ``SV0_MCP_PROGRESS_DASHBOARD`` — set to ``0`` / ``false`` / ``no`` to disable.
* ``SV0_MCP_PROGRESS_DASHBOARD_PORT`` — TCP port (default ``8765``).
* ``SV0_MCP_PROGRESS_DASHBOARD_REFRESH`` — server-side digest cache TTL in
  seconds (default ``120``).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path  # noqa: TC003

logger = logging.getLogger(__name__)


def _progress_script(toolchain_root: Path) -> Path | None:
    script = toolchain_root / "scripts" / "progress_dashboard_server.py"
    return script if script.is_file() else None


def _truthy_env(name: str, default: str = "1") -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw not in ("0", "false", "no", "off")


def start_with_mcp(toolchain_root: Path) -> subprocess.Popen[bytes] | None:
    """Spawn the progress dashboard if enabled and the script exists.

    Args:
        toolchain_root: Resolved sv0-toolchain meta-repo root.

    Returns:
        A :class:`subprocess.Popen` for the child, or ``None`` if not started.
    """
    if not _truthy_env("SV0_MCP_PROGRESS_DASHBOARD", "1"):
        logger.info("progress dashboard: disabled (SV0_MCP_PROGRESS_DASHBOARD=0)")
        return None
    script = _progress_script(toolchain_root)
    if script is None:
        logger.warning(
            "progress dashboard: skipped (missing %s)",
            toolchain_root / "scripts" / "progress_dashboard_server.py",
        )
        return None
    port = os.environ.get("SV0_MCP_PROGRESS_DASHBOARD_PORT", "8765").strip() or "8765"
    refresh = (
        os.environ.get("SV0_MCP_PROGRESS_DASHBOARD_REFRESH", "120").strip() or "120"
    )
    cmd = [
        sys.executable,
        str(script),
        "--root",
        str(toolchain_root.resolve()),
        "--port",
        port,
        "--refresh-seconds",
        refresh,
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(toolchain_root.resolve()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("progress dashboard: failed to start: %s", exc)
        return None
    logger.info(
        "progress dashboard: child pid %s (http://127.0.0.1:%s/)",
        proc.pid,
        port,
    )
    return proc


def stop_child(proc: subprocess.Popen[bytes] | None) -> None:
    """Terminate the dashboard child if it is still running."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        logger.warning("progress dashboard: killing pid %s after timeout", proc.pid)
        proc.kill()
        proc.wait(timeout=3)
