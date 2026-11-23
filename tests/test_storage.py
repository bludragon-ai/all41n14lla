"""Lifecycle + reconcile tests for Storage."""
from __future__ import annotations

from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.search import search
from all41n14lla.engine.storage import (
    NODE_FOLDERS,
    Storage,
    default_db_path,
    folder_for,
)


def _make_vault(root: Path) -> Path:
    for folder in NODE_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def test_schema_initialized(tmp_path: Path):
    db = tmp_path / "index.db"
    with Storage(db) as s:
        names = {
            row["name"]
            for row in s.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
            ).fetchall()
        }
    assert {"nodes", "nodes_fts", "edges"}.issubset(names)


def test_write_read_update_delete(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    db = default_db_path(vault)

    node = MemoryNode(
        type=NodeType.CONCEPT,
        content="Memory should live on disk.",
        tags=["thesis", "architecture"],
    )
    node.write(vault / folder_for(NodeType.CONCEPT) / f"{node.id}.md")

    with Storage(db) as s:
        s.upsert_node(node)
        row = s.get_node_row(node.id)
        assert row is not None
        assert row["type"] == "concept"

        # Update path (simulate re-save)
        node.updated = node.updated.replace(microsecond=999999)
        s.upsert_node(node)
        assert s.get_node_row(node.id) is not None

        # Delete
        assert s.delete_node(node.id) is True
        assert s.get_node_row(node.id) is None


def test_fts_search_finds_match(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    db = default_db_path(vault)

    concept = MemoryNode(
        type=NodeType.CONCEPT,
        content="Portable memory for AI agents lives in markdown.",
        tags=["portability"],
    )
    episode = MemoryNode(
        type=NodeType.EPISODE,
        content="Wrote the first test for storage reconciliation.",
        tags=["test", "storage"],
    )
    concept.write(vault / folder_for(NodeType.CONCEPT) / f"{concept.id}.md")
    episode.write(vault / folder_for(NodeType.EPISODE) / f"{episode.id}.md")

    with Storage(db) as s:
        s.upsert_node(concept)
        s.upsert_node(episode)

        hits = search(s, "markdown")
        ids = [n.id for n, _ in hits]
        assert concept.id in ids

        hits_typed = search(s, "storage", node_type=NodeType.EPISODE)
        ids_typed = [n.id for n, _ in hits_typed]
        assert episode.id in ids_typed
        assert concept.id not in ids_typed


def test_reconcile_picks_up_manual_file(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    db = default_db_path(vault)

    # Manual file — as if a user dropped one in Obsidian.
    manual = MemoryNode(
        type=NodeType.CONSTRAINT,
        content="Never commit secrets.",
        tags=["security"],
    )
    manual.write(vault / folder_for(NodeType.CONSTRAINT) / f"{manual.id}.md")

    with Storage(db) as s:
        indexed, removed = s.reconcile(vault)
        assert indexed == 1
        assert removed == 0
        assert s.get_node_row(manual.id) is not None


def test_reconcile_drops_vanished_files(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    db = default_db_path(vault)

    ghost = MemoryNode(type=NodeType.PATTERN, content="Soon to vanish.")
    ghost_path = vault / folder_for(NodeType.PATTERN) / f"{ghost.id}.md"
    ghost.write(ghost_path)

    with Storage(db) as s:
        s.upsert_node(ghost)
        ghost_path.unlink()
        _, removed = s.reconcile(vault)
        assert removed == 1
        assert s.get_node_row(ghost.id) is None
