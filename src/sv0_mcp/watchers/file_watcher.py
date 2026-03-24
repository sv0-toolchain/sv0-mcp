"""File watcher daemon using the watchdog library for sv0-toolchain monitoring."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable  # noqa: TC003
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from sv0_mcp.config import Sv0McpSettings
    from sv0_mcp.graph.sync import GraphSyncEngine

logger = logging.getLogger(__name__)

_SUBPROJECT_SCOPE_MAP: dict[str, str] = {
    "sv0doc": "spec",
    "sv0c": "compiler",
    "sv0vm": "vm",
    "task": "tasks",
}


class ScopeMapping:
    """Maps file paths to sync scopes based on subproject directory and file extension."""

    EXTENSION_MAP: ClassVar[dict[str, str]] = {
        ".ebnf": "spec",
        ".md": "spec",
        ".sml": "compiler",
        ".sig": "compiler",
        ".cm": "compiler",
        ".Rmd": "tasks",
    }

    @staticmethod
    def path_to_scope(path: Path, toolchain_root: Path) -> str | None:
        """Determine sync scope from a file path.

        Resolves scope by checking the file's relative path against known
        subproject directories (sv0doc -> spec, sv0c -> compiler, sv0vm -> vm,
        task -> tasks). Falls back to extension-based mapping when the
        subproject cannot be determined from the directory.

        Args:
            path: Absolute or relative path to the changed file.
            toolchain_root: Root directory of the sv0-toolchain.

        Returns:
            The scope string, or ``None`` if the path does not map to any scope.
        """
        try:
            relative = path.resolve().relative_to(toolchain_root.resolve())
        except ValueError:
            return None

        parts = relative.parts
        if not parts:
            return None

        top_dir = parts[0]
        if top_dir in _SUBPROJECT_SCOPE_MAP:
            return _SUBPROJECT_SCOPE_MAP[top_dir]

        suffix = path.suffix
        return ScopeMapping.EXTENSION_MAP.get(suffix)


class Sv0ChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers graph syncs with debouncing.

    The debounce mechanism tracks the last sync time per scope and uses
    ``threading.Timer`` to coalesce rapid changes into a single sync call.
    """

    def __init__(
        self,
        sync_callback: Callable[[str], None],
        toolchain_root: Path,
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize the change handler.

        Args:
            sync_callback: Function to call with the scope name when sync is needed.
            toolchain_root: Root directory of the sv0-toolchain.
            debounce_seconds: Minimum interval between syncs for the same scope.
        """
        super().__init__()
        self._sync_callback = sync_callback
        self._toolchain_root = toolchain_root
        self._debounce_seconds = debounce_seconds
        self._last_sync: dict[str, float] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            self._handle_change(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            self._handle_change(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            self._handle_change(str(event.src_path))

    def _handle_change(self, path: str) -> None:
        """Debounce and trigger sync for the appropriate scope.

        If ``debounce_seconds`` have elapsed since the last sync for this scope,
        the callback fires immediately. Otherwise a ``threading.Timer`` delays
        execution until the debounce window expires.

        Args:
            path: Absolute path of the changed file.
        """
        scope = ScopeMapping.path_to_scope(Path(path), self._toolchain_root)
        if scope is None:
            return

        with self._lock:
            now = time.monotonic()
            last = self._last_sync.get(scope, 0.0)
            elapsed = now - last

            if scope in self._timers:
                self._timers[scope].cancel()

            if elapsed >= self._debounce_seconds:
                self._last_sync[scope] = now
                logger.info("Triggering immediate sync for scope: %s", scope)
                self._sync_callback(scope)
            else:
                delay = self._debounce_seconds - elapsed
                logger.debug(
                    "Debouncing sync for scope %s (%.2fs remaining)", scope, delay
                )
                timer = threading.Timer(delay, self._fire_sync, args=(scope,))
                self._timers[scope] = timer
                timer.start()

    def _fire_sync(self, scope: str) -> None:
        """Fire a debounced sync after the timer expires.

        Called from a ``threading.Timer`` thread. Updates bookkeeping under the
        lock before invoking the sync callback.

        Args:
            scope: The sync scope to trigger.
        """
        with self._lock:
            self._last_sync[scope] = time.monotonic()
            self._timers.pop(scope, None)
        logger.info("Triggering debounced sync for scope: %s", scope)
        self._sync_callback(scope)


class FileWatcherDaemon:
    """Watches sv0-toolchain directories for changes and triggers graph sync.

    Monitors ``sv0doc/``, ``sv0c/``, ``sv0vm/``, and ``task/`` subdirectories
    within the toolchain root using the watchdog ``Observer``.
    """

    WATCH_DIRS: ClassVar[list[str]] = ["sv0doc", "sv0c", "sv0vm", "task"]

    def __init__(self, settings: Sv0McpSettings, sync_engine: GraphSyncEngine) -> None:
        """Initialize the file watcher daemon.

        Args:
            settings: Application settings containing the toolchain root path.
            sync_engine: The graph sync engine to trigger on file changes.
        """
        self._settings = settings
        self._sync_engine = sync_engine
        self._observer = Observer()
        self._toolchain_root = Path(settings.toolchain_root)

    def start(self) -> None:
        """Start watching. Blocks until ``stop()`` is called or interrupted."""
        self._setup_watches()
        self._observer.start()
        logger.info("File watcher started for %s", self._toolchain_root)
        try:
            while self._observer.is_alive():
                self._observer.join(timeout=1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the watcher and wait for the observer thread to finish."""
        logger.info("Stopping file watcher")
        self._observer.stop()
        self._observer.join()

    def _setup_watches(self) -> None:
        """Set up file system watches on sv0doc/, sv0c/, sv0vm/, task/ directories."""
        handler = Sv0ChangeHandler(
            sync_callback=self._trigger_sync,
            toolchain_root=self._toolchain_root,
        )
        for dir_name in self.WATCH_DIRS:
            watch_path = self._toolchain_root / dir_name
            if watch_path.is_dir():
                self._observer.schedule(handler, str(watch_path), recursive=True)
                logger.info("Watching %s", watch_path)
            else:
                logger.warning("Directory not found, skipping watch: %s", watch_path)

    def _trigger_sync(self, scope: str) -> None:
        """Trigger a graph sync for the given scope.

        Args:
            scope: The sync scope string to execute.
        """
        from sv0_mcp.graph.sync import SyncScope  # noqa: PLC0415

        try:
            self._sync_engine.sync(SyncScope(scope))
        except Exception:
            logger.exception("Sync failed for scope: %s", scope)
