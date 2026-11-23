"""Verifiable erasure: forget by source, get a receipt, re-scan proves zero remain."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from all41n14lla.cli import app
from all41n14lla.devour import analyze, consume
from all41n14lla.erase import find_by_source, rescan
from all41n14lla.reincarnate import reincarnate


def _prey(tmp_path: Path) -> Path:
    root = tmp_path / "prey"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Ops\n\nHow it runs.\n\n- Never text after 9pm.\n", encoding="utf-8")
    (root / "docs" / "a.md").write_text("# A\n\nAlpha.\n", encoding="utf-8")
    (root / "app.py").write_text('"""Engine."""\n', encoding="utf-8")
    return root


def _fed_vault(tmp_path: Path):
    vault = tmp_path / "v"
    reincarnate(vault, {"name": "N", "address": "A", "tone": "t", "north_star": "typed, not devoured"}, say=lambda s: None)
    consume(vault, analyze(_prey(tmp_path)), None, say=lambda s: None)
    return vault


def _ids(vault: Path) -> set[str]:
    return {p.stem for p in vault.rglob("*.md") if p.parent != vault}


def test_forget_by_source_erases_only_that_source_and_writes_a_receipt(tmp_path):
    vault = _fed_vault(tmp_path)
    before = _ids(vault)
    assert len(find_by_source(vault, "README.md")) == 2  # concept + the never-rule
    result = CliRunner().invoke(app, ["forget", "--source", "README.md", "--yes", "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert "Erased 2" in result.output and "0 remain" in result.output
    assert rescan(vault, "README.md") == 0
    after = _ids(vault)
    assert len(before - after) == 2
    # the typed north star, the birth episode, docs/a.md and app.py survive
    assert len(find_by_source(vault, "docs/a.md")) == 1
    assert len(find_by_source(vault, "app.py")) == 1
    receipts = list((vault / ".all41n14lla" / "erasures").glob("*.json"))
    assert len(receipts) == 1
    r = json.loads(receipts[0].read_text())
    assert r["source"] == "README.md" and r["count"] == 2 and r["remaining_after_rescan"] == 0
    assert all(len(d["content_sha256"]) == 64 for d in r["deleted"])
    assert {d["id"] for d in r["deleted"]} == before - after


def test_source_prefix_and_glob(tmp_path):
    vault = _fed_vault(tmp_path)
    assert len(find_by_source(vault, "docs")) == 1
    assert len(find_by_source(vault, "docs/")) == 1
    assert len(find_by_source(vault, "*.py")) == 1
    assert find_by_source(vault, "nothing-here") == []


def test_forget_source_with_no_match_writes_no_receipt(tmp_path):
    vault = _fed_vault(tmp_path)
    result = CliRunner().invoke(app, ["forget", "--source", "ghost.md", "--yes", "--vault", str(vault)])
    assert result.exit_code == 1
    assert not (vault / ".all41n14lla" / "erasures").exists()


def test_forget_source_aborts_without_consent(tmp_path):
    vault = _fed_vault(tmp_path)
    before = _ids(vault)
    result = CliRunner().invoke(app, ["forget", "--source", "README.md", "--vault", str(vault)], input="n\n")
    assert result.exit_code == 0 and "Nothing erased" in result.output
    assert _ids(vault) == before


def test_forget_by_id_still_works_and_now_leaves_a_receipt(tmp_path):
    vault = _fed_vault(tmp_path)
    target = find_by_source(vault, "app.py")[0]
    result = CliRunner().invoke(app, ["forget", target.id[:8], "--yes", "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert target.id not in _ids(vault)
    receipts = list((vault / ".all41n14lla" / "erasures").glob("*.json"))
    assert len(receipts) == 1
    r = json.loads(receipts[0].read_text())
    assert r["source"] is None and r["count"] == 1 and r["remaining_after_rescan"] == 0
