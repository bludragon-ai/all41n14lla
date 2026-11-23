"""Tests for the watchdog vault reconciler.

These tests exercise the event-handler logic directly (without spinning up a
real Observer thread) so the tests are deterministic and fast. Live-observer
smoke is covered manually in the dev workflow.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path, folder_for
from all41n14lla.watcher import VaultEventHandler


def _make_vault(root: Path) -> Path:
    for folder in NODE_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def _fake_event(path: Path, dest_path: Path | None = None) -> SimpleNamespace:
    """Build a minimal object that quacks like a watchdog FileSystemEvent."""
    return SimpleNamespace(
        src_path=str(path),
        dest_path=str(dest_path) if dest_path else str(path),
        is_directory=False,
    )


def test_is_vault_node_accepts_typed_markdown(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    good = vault / "concepts" / "abc.md"
    assert h._is_vault_node(good) is True


def test_is_vault_node_rejects_outside(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    # Non-md
    assert h._is_vault_node(vault / "concepts" / "abc.txt") is False
    # Wrong folder
    assert h._is_vault_node(vault / "random" / "abc.md") is False
    # Outside the vault entirely
    assert h._is_vault_node(tmp_path / "other" / "abc.md") is False
    # Nested too deep
    assert h._is_vault_node(vault / "concepts" / "sub" / "abc.md") is False


def test_on_created_indexes_new_file(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    node = MemoryNode(type=NodeType.CONCEPT, content="Watcher picks this up.")
    file_path = vault / folder_for(NodeType.CONCEPT) / f"{node.id}.md"
    node.write(file_path)

    h.on_created(_fake_event(file_path))

    with Storage(default_db_path(vault)) as s:
        row = s.get_node_row(node.id)
        assert row is not None
        assert row["type"] == "concept"


def test_on_modified_updates_index(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    node = MemoryNode(type=NodeType.PATTERN, content="Original text.")
    file_path = vault / folder_for(NodeType.PATTERN) / f"{node.id}.md"
    node.write(file_path)
    h.on_created(_fake_event(file_path))

    # Hand-edit: rewrite content and re-save (same id).
    node.content = "Updated text."
    node.write(file_path)
    h.on_modified(_fake_event(file_path))

    with Storage(default_db_path(vault)) as s:
        hits = s.conn.execute(
            "SELECT content FROM nodes_fts WHERE id = ?", (node.id,)
        ).fetchall()
        assert hits
        assert "Updated text." in hits[0]["content"]


def test_on_deleted_drops_index_row(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    node = MemoryNode(type=NodeType.EPISODE, content="Ephemeral.")
    file_path = vault / folder_for(NodeType.EPISODE) / f"{node.id}.md"
    node.write(file_path)
    h.on_created(_fake_event(file_path))

    file_path.unlink()
    h.on_deleted(_fake_event(file_path))

    with Storage(default_db_path(vault)) as s:
        assert s.get_node_row(node.id) is None


def test_ignores_non_node_files(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    h = VaultEventHandler(vault)

    # A file that passes through on_created but isn't a node — should be a no-op.
    junk = vault / "concepts" / "not-really-a-node.txt"
    junk.write_text("nope", encoding="utf-8")

    h.on_created(_fake_event(junk))

    with Storage(default_db_path(vault)) as s:
        rows = s.conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()
        assert rows["c"] == 0
