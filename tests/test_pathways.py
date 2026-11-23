"""Tests for the pathways edges table and ``increment_edges``."""
from __future__ import annotations

from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
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


def _persist_concept(vault: Path, storage: Storage, text: str) -> str:
    node = MemoryNode(type=NodeType.CONCEPT, content=text)
    node.write(vault / folder_for(NodeType.CONCEPT) / f"{node.id}.md")
    storage.upsert_node(node)
    return node.id


def test_increment_edges_ignores_fewer_than_two_ids(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        assert s.increment_edges([]) == 0
        assert s.increment_edges(["only-one"]) == 0


def test_increment_edges_first_pass_inserts_pairs(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _persist_concept(vault, s, "A")
        b = _persist_concept(vault, s, "B")
        c = _persist_concept(vault, s, "C")

        pairs = s.increment_edges([a, b, c])
        assert pairs == 3  # 3 choose 2 = 3 unique pairs

        rows = s.conn.execute(
            "SELECT src_id, dst_id, weight FROM edges ORDER BY src_id, dst_id"
        ).fetchall()
        assert len(rows) == 3
        for row in rows:
            assert row["weight"] == 1.0
            assert row["src_id"] < row["dst_id"]  # canonical ordering


def test_increment_edges_second_pass_increments_weight(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _persist_concept(vault, s, "A")
        b = _persist_concept(vault, s, "B")

        s.increment_edges([a, b])
        s.increment_edges([a, b])
        s.increment_edges([a, b])

        rows = s.conn.execute("SELECT weight FROM edges").fetchall()
        assert len(rows) == 1
        assert rows[0]["weight"] == 3.0


def test_increment_edges_dedupes_input(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _persist_concept(vault, s, "A")
        b = _persist_concept(vault, s, "B")

        # Duplicate ids in the input shouldn't create self-pairs or duplicate rows.
        s.increment_edges([a, a, b, b])

        rows = s.conn.execute("SELECT src_id, dst_id FROM edges").fetchall()
        assert len(rows) == 1  # one pair only
        assert rows[0]["src_id"] != rows[0]["dst_id"]  # never a self-edge
