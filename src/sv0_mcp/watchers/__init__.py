"""Watchers package for sv0-mcp file system monitoring and git hook management."""

from __future__ import annotations

from sv0_mcp.watchers.file_watcher import FileWatcherDaemon, ScopeMapping, Sv0ChangeHandler
from sv0_mcp.watchers.git_hooks import generate_hook, install_hooks, uninstall_hooks

__all__ = [
    "FileWatcherDaemon",
    "ScopeMapping",
    "Sv0ChangeHandler",
    "generate_hook",
    "install_hooks",
    "uninstall_hooks",
]
