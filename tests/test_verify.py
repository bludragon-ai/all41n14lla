"""Tests for the opt-in verified-recall post-filter (engine/verify.py).

The judge is mocked throughout — no test here talks to a real ollama. The
contract under test: verify=False is byte-identical to before, verify=True
drops IRRELEVANT hits, ollama failure degrades gracefully, empty results
never touch the network, and floor constraints are never dropped.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from all41n14lla.engine import verify as verify_mod
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


def _explode(*args, **kwargs):
    raise AssertionError("ollama must not be called on this path")


def test_verify_false_path_unchanged(scratch_vault: Path, monkeypatch):
    """Default recall never touches the verifier and returns no `verified` key."""
    from all41n14lla.server import recall, remember

    monkeypatch.setattr(verify_mod, "_judge", _explode)
    monkeypatch.setattr(verify_mod.httpx, "Client", _explode)

    remember(type="concept", content="Portable memory lives on disk.")
    hits = recall(query="portable")
    assert len(hits) == 1
    assert "verified" not in hits[0]


def test_verify_true_drops_irrelevant_hits(scratch_vault: Path, monkeypatch):
    from all41n14lla.server import recall, remember

    remember(type="concept", content="Python packaging uses pyproject.toml.")
    remember(type="concept", content="Python snakes live in packaging crates at the zoo.")

    monkeypatch.setattr(
        verify_mod, "_judge", lambda client, query, content: "zoo" not in content
    )
    hits = recall(query="python packaging", verify=True)
    assert len(hits) == 1
    assert "zoo" not in hits[0]["content"]
    assert hits[0]["verified"] is True


def test_ollama_down_returns_unfiltered_with_flag(scratch_vault: Path, monkeypatch):
    from all41n14lla.server import recall, remember

    remember(type="concept", content="First fact about widgets.")
    remember(type="concept", content="Second fact about widgets.")

    def _down(*args, **kwargs):
        raise verify_mod.httpx.ConnectError("connection refused")

    monkeypatch.setattr(verify_mod, "_judge", _down)
    hits = recall(query="widgets", verify=True)
    assert len(hits) == 2
    assert all(h["verified"] is False for h in hits)


def test_empty_results_short_circuit(scratch_vault: Path, monkeypatch):
    from all41n14lla.server import recall

    monkeypatch.setattr(verify_mod, "_judge", _explode)
    monkeypatch.setattr(verify_mod.httpx, "Client", _explode)
    assert recall(query="nothing stored yet", verify=True) == []


def test_floor_constraints_never_judged_or_dropped(scratch_vault: Path, monkeypatch):
    """The constraint floor is a deterministic guarantee — verify can't veto it."""
    from all41n14lla.server import recall, remember

    remember(
        type="constraint",
        content="Never commit secrets.",
        tags=["secrets"],
    )
    monkeypatch.setattr(verify_mod, "_judge", lambda *a, **k: False)  # drop everything
    hits = recall(query="secrets", verify=True)
    assert len(hits) == 1
    assert hits[0]["floor"] is True
    assert hits[0]["verified"] is True
