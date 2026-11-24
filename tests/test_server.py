"""Smoke tests for the MCP server module.

Full protocol-level tests (stdio handshake, JSON-RPC framing) require launching
the server as a subprocess — we do that in Step 5 expanded suite. For v0.1 we
verify tool functions are registered, callable, and touch the engine correctly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path


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


def test_forget_writes_an_erase_receipt_with_rescan(scratch_vault: Path):
    import hashlib
    import json

    from all41n14lla.server import forget, remember

    content = "A receipt must vouch for this without keeping it."
    written = remember(type="concept", content=content)
    erasures = scratch_vault / ".all41n14lla" / "erasures"
    assert not erasures.exists()

    result = forget(id=written["id"][:8])
    assert result["deleted"] is True and result["id"] == written["id"]
    assert result["remaining_after_rescan"] == 0

    receipts = list(erasures.glob("*.json"))
    assert len(receipts) == 1
    assert Path(result["receipt"]) == receipts[0]
    raw = receipts[0].read_text()
    assert content not in raw
    r = json.loads(raw)
    assert r["source"] is None and r["count"] == 1 and r["remaining_after_rescan"] == 0
    assert r["deleted"][0]["id"] == written["id"]
    assert r["deleted"][0]["content_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_forget_when_file_already_gone_clears_the_index_and_says_so(scratch_vault: Path):
    from all41n14lla.server import forget, recall, remember

    written = remember(type="episode", content="Vanished from disk before the forget call.")
    Path(written["path"]).unlink()

    result = forget(id=written["id"])
    assert result["deleted"] is True and result["id"] == written["id"]
    assert result["receipt"] is None and "already gone" in result["reason"]
    assert recall(query="Vanished") == []


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


def test_identity_returns_none_persona_when_unset(scratch_vault: Path):
    from all41n14lla.server import identity

    result = identity()
    assert result["vault"] == str(scratch_vault)
    assert result["persona"] is None


def test_identity_returns_persona_when_set(scratch_vault: Path):
    from all41n14lla.persona import Persona, write_persona
    from all41n14lla.server import identity

    write_persona(scratch_vault, Persona("Aster", "Captain", "warm and direct"))

    result = identity()
    assert result["persona"] is not None
    assert "Aster" in result["persona"]


def test_guard_output_passes_non_repetitive_text(scratch_vault: Path):
    from all41n14lla.server import guard_output

    result = guard_output(chunks=["This is one sentence. ", "This is a different one."])
    assert result["loop_detected"] is False
    assert "different one" in result["text"]


def test_guard_output_cuts_immediate_repeat(scratch_vault: Path):
    from all41n14lla.server import guard_output

    repeated = "This short sentence repeats immediately. "
    result = guard_output(chunks=[repeated, repeated])
    assert result["loop_detected"] is True
    assert result["match"] is not None
