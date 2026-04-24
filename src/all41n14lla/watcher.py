"""Live vault reconciliation via watchdog.

When the MCP server runs, a VaultObserver watches the vault's four node-type
folders and reconciles hand-edits into the SQLite index as they happen. The
observer is idempotent: reloading a file we just wrote is harmless because
``Storage.upsert_node`` is an UPSERT.

The observer runs in a daemon thread so it exits cleanly when the main
server process terminates.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from all41n14lla.engine.nodes import MemoryNode
from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path


class VaultEventHandler(FileSystemEventHandler):
    """Reconciles filesystem changes in the vault into the SQLite index."""

    def __init__(self, vault: Path):
        self.vault = Path(vault).expanduser().resolve()
        self.db_path = default_db_path(self.vault)
        self._lock = threading.Lock()

    def _is_vault_node(self, path: Path) -> bool:
        """Return True if `path` is a markdown file inside a node-type folder."""
        if path.suffix != ".md":
            return False
        # Must live at <vault>/<type-folder>/<file>.md
        try:
            parent = path.parent
            if parent.parent != self.vault:
                return False
            if parent.name not in NODE_FOLDERS:
                return False
        except (OSError, ValueError):
            return False
        return True

    def _upsert(self, path: Path) -> None:
        with self._lock:
            try:
                node = MemoryNode.from_file(path)
            except Exception:
                return
            with Storage(self.db_path) as storage:
                storage.upsert_node(node)

    def _delete(self, path: Path) -> None:
        # We only know the path; the node id lives inside the file, which is
        # gone. Scan the index for rows whose path matches and drop them.
        with self._lock:
            with Storage(self.db_path) as storage:
                rows = storage.conn.execute(
                    "SELECT id FROM nodes WHERE path = ?", (str(path),)
                ).fetchall()
                for row in rows:
                    storage.delete_node(row["id"])

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._is_vault_node(path):
            self._upsert(path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._is_vault_node(path):
            self._upsert(path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._is_vault_node(path):
            self._delete(path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = Path(event.src_path)
        dst = Path(getattr(event, "dest_path", str(src)))
        if self._is_vault_node(src):
            self._delete(src)
        if self._is_vault_node(dst):
            self._upsert(dst)


def start_observer(vault: Path) -> Optional[Observer]:
    """Start a recursive observer on the vault. Returns the observer (or None
    if the vault does not exist).

    Caller is responsible for calling ``observer.stop()`` and
    ``observer.join()`` on shutdown.
    """
    vault = Path(vault).expanduser().resolve()
    if not vault.exists():
        return None
    handler = VaultEventHandler(vault)
    observer = Observer()
    observer.schedule(handler, str(vault), recursive=True)
    observer.daemon = True
    observer.start()
    return observer
