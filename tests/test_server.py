"""Smoke tests for the MCP server module.

Full protocol-level tests (stdio handshake, JSON-RPC framing) require launching
the server as a subprocess — we do that in Step 5 expanded suite. For v0.1 we
verify tool functions are registered, callable, and touch the engine correctly.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from all41n14lla.engine.nodes import NodeType
from all41n14lla.engine.storage import NODE_FOLDERS, default_db_path, Storage


def _make_vault(root: Path) -> Path:
    for folder in NODE_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    with Storage(default_db_path(root)):
        pass
    return root


@pytest.fixture
def scratch_vault(tmp_path: Path, monkeypatch) -> Path:
    vault = _make_vault(tmp_path / "vault")
    monkeypatch.setenv("ALL41N14LLA_VAULT", str(vault))
    return vault


def test_server_module_imports():
    """Importing the server should register the FastMCP tools without errors."""
    from all41n14lla import server

    assert server.mcp is not None
    assert callable(server.main)


def test_remember_and_recall_via_tool_functions(scratch_vault: Path):
    from all41n14lla.server import recall, remember

    written = remember(
        type="concept",
        content="Portable memory should live on disk.",
        tags=["thesis"],
    )
    assert "id" in written
    assert written["type"] == "concept"
    assert Path(written["path"]).exists()

    hits = recall(query="portable", limit=5)
    assert len(hits) == 1
    assert hits[0]["id"] == written["id"]
    assert hits[0]["type"] == "concept"


def test_forget_removes_file_and_index_row(scratch_vault: Path):
    from all41n14lla.server import forget, recall, remember

    written = remember(type="episode", content="Shipped v0.1 on a Friday.")
    assert Path(written["path"]).exists()

    result = forget(id=written["id"])
    assert result["deleted"] is True
    assert result["id"] == written["id"]
    assert not Path(written["path"]).exists()

    hits = recall(query="Friday")
    assert hits == []


def test_forget_reports_ambiguous_prefix(scratch_vault: Path):
    from all41n14lla.server import forget

    result = forget(id="")
    assert result["deleted"] is False
    # Empty prefix matches everything — 0 or ambiguous, either way not deleted.


def test_consolidate_returns_stub_status(scratch_vault: Path):
    from all41n14lla.server import consolidate

    result = consolidate()
    assert result["status"] == "pending_v0.2.0"


def test_recall_type_filter(scratch_vault: Path):
    from all41n14lla.server import recall, remember

    remember(type="concept", content="Concepts are stable ideas.")
    remember(type="episode", content="Concepts feel stable to write about today.")

    concept_hits = recall(query="stable", type="concept")
    assert len(concept_hits) == 1
    assert concept_hits[0]["type"] == "concept"


def test_vault_env_var_overrides_default(tmp_path: Path, monkeypatch):
    from all41n14lla.server import _vault_path

    target = tmp_path / "custom-vault"
    target.mkdir()
    monkeypatch.setenv("ALL41N14LLA_VAULT", str(target))
    assert _vault_path() == target.resolve()
