"""SQLite index for all41n14lla.

Markdown files on disk are the canonical source of truth. This module maintains a
SQLite database at ``<vault>/.all41n14lla/index.db`` that mirrors the on-disk state
for fast lookup and full-text search.

Schema
------
``nodes``      one row per memory file (id, type, path, timestamps, stale, decay)
``nodes_fts``  FTS5 virtual table on ``content`` and ``tags``, Porter tokenizer
``edges``      co-occurrence edges between concept ids (for pathways)

Thread-safety
-------------
Intended for single-process use. The connection is opened with WAL mode so readers
never block writers. The class is a context manager; open it, do work, close it.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from all41n14lla.engine.nodes import MemoryNode, NodeType


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id       TEXT PRIMARY KEY,
    type     TEXT NOT NULL,
    path     TEXT NOT NULL UNIQUE,
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL,
    stale    INTEGER NOT NULL DEFAULT 0,
    decay    REAL NOT NULL DEFAULT 0.0
);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id UNINDEXED,
    content,
    tags,
    tokenize='porter'
);

CREATE TABLE IF NOT EXISTS edges (
    src_id  TEXT NOT NULL,
    dst_id  TEXT NOT NULL,
    weight  REAL NOT NULL DEFAULT 1.0,
    updated TEXT NOT NULL,
    PRIMARY KEY (src_id, dst_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_type  ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_stale ON nodes(stale);
"""


NODE_FOLDERS = ("concepts", "patterns", "episodes", "constraints")


def folder_for(node_type: NodeType) -> str:
    """Return the plural folder name for a NodeType."""
    return f"{node_type.value}s"


class Storage:
    """Context-managed wrapper around the SQLite index."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "Storage":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        self._conn = conn
        return self

    def __exit__(self, *exc) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Storage is not open — use as a context manager")
        return self._conn

    def upsert_node(self, node: MemoryNode) -> None:
        if node.path is None:
            raise ValueError("Node must be written to disk (node.path set) before indexing")
        self.conn.execute(
            """
            INSERT INTO nodes (id, type, path, created, updated, stale, decay)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type    = excluded.type,
                path    = excluded.path,
                updated = excluded.updated,
                stale   = excluded.stale,
                decay   = excluded.decay
            """,
            (
                node.id,
                node.type.value,
                str(node.path),
                node.created.isoformat(),
                node.updated.isoformat(),
                int(node.stale),
                node.decay,
            ),
        )
        self.conn.execute("DELETE FROM nodes_fts WHERE id = ?", (node.id,))
        self.conn.execute(
            "INSERT INTO nodes_fts (id, content, tags) VALUES (?, ?, ?)",
            (node.id, node.content, " ".join(node.tags)),
        )
        self.conn.commit()

    def delete_node(self, node_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.conn.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_node_row(self, node_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()

    def list_nodes(self, node_type: Optional[NodeType] = None) -> list[sqlite3.Row]:
        if node_type is not None:
            sql = "SELECT * FROM nodes WHERE type = ? ORDER BY updated DESC"
            return self.conn.execute(sql, (node_type.value,)).fetchall()
        return self.conn.execute(
            "SELECT * FROM nodes ORDER BY updated DESC"
        ).fetchall()

    def reconcile(self, vault_path: Path) -> tuple[int, int]:
        """Scan vault folders, reindex every valid file, drop rows whose files vanished.

        Returns ``(indexed, removed)``.
        """
        vault_path = Path(vault_path)
        seen: set[str] = set()
        indexed = 0
        for folder in NODE_FOLDERS:
            folder_path = vault_path / folder
            if not folder_path.exists():
                continue
            for md_file in folder_path.glob("*.md"):
                try:
                    node = MemoryNode.from_file(md_file)
                except Exception:
                    continue
                self.upsert_node(node)
                seen.add(node.id)
                indexed += 1
        existing = {
            row["id"]
            for row in self.conn.execute("SELECT id FROM nodes").fetchall()
        }
        stale_ids = existing - seen
        for sid in stale_ids:
            self.delete_node(sid)
        return indexed, len(stale_ids)


def default_db_path(vault_path: Path) -> Path:
    """Canonical index location for a given vault."""
    return Path(vault_path) / ".all41n14lla" / "index.db"
