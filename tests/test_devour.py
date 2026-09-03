"""Predator: proposes, never writes without consent; provenance on everything it writes."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from all41n14lla.cli import app
from all41n14lla.devour import analyze, consume, existing_source_hashes, parse_accept
from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.reincarnate import reincarnate


@pytest.fixture
def prey(tmp_path: Path) -> Path:
    root = tmp_path / "prey"
    (root / "docs").mkdir(parents=True)
    (root / "node_modules" / "junk").mkdir(parents=True)
    (root / "README.md").write_text(
        "# Salon Ops\n\nHow the front desk runs when nobody is at it.\n\n"
        "## Rules\n- Never text a client after 9pm.\n- Always confirm the day before.\n- ok\n",
        encoding="utf-8",
    )
    (root / "docs" / "notes.md").write_text("plain note with no heading\n", encoding="utf-8")
    (root / "app.py").write_text('"""Booking engine: one function, one calendar."""\n\ndef book(): ...\n', encoding="utf-8")
    (root / "node_modules" / "junk" / "x.md").write_text("# Never read me\n\ninside node_modules\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    (root / "huge.md").write_text("# Big\n\n" + "x" * 250_000, encoding="utf-8")
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "v"
    reincarnate(v, {"name": "N", "address": "A", "tone": "t"}, say=lambda s: None)
    return v


def _files(vault: Path) -> set[Path]:
    return {p for p in vault.rglob("*.md") if p.parent != vault}


def test_analyze_proposes_the_right_things(prey):
    a = analyze(prey)
    kinds = [(c.kind, c.where) for c in a.candidates]
    assert (NodeType.CONCEPT, "README.md:1") in kinds
    assert (NodeType.CONSTRAINT, "README.md:6") in kinds  # Never text a client after 9pm
    assert (NodeType.CONSTRAINT, "README.md:7") in kinds  # Always confirm the day before
    assert (NodeType.CONCEPT, "app.py:1") in kinds
    assert (NodeType.CONCEPT, "docs/notes.md:1") in kinds
    assert not any("node_modules" in c.where for c in a.candidates)
    assert a.files_skipped >= 2  # png + huge
    rule = next(c for c in a.candidates if c.where == "README.md:6")
    assert "send" in rule.tags and rule.content.startswith("Never text a client")


def test_without_accept_nothing_is_written(prey, vault):
    """The negative claim is the product: no consent, no write."""
    before = _files(vault)
    result = CliRunner().invoke(app, ["devour", str(prey), "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert "Nothing devoured" in result.output
    assert _files(vault) == before


def test_accept_all_writes_with_provenance(prey, vault):
    result = CliRunner().invoke(app, ["devour", str(prey), "--vault", str(vault), "--accept", "all"])
    assert result.exit_code == 0, result.output
    assert result.output.count("《Confirmed.》") >= 5
    new = [MemoryNode.from_file(p) for p in _files(vault)]
    devoured = [n for n in new if n.source]
    assert len(devoured) == 5
    for n in devoured:
        assert n.source_hash and len(n.source_hash) == 64
        assert "devoured" in n.tags
        # the frontmatter carries it — re-read from disk, not from memory
        assert "source_hash:" in n.path.read_text()
    meal = [n for n in new if n.type is NodeType.EPISODE and "devour" in n.tags]
    assert len(meal) == 1 and set(meal[0].links) == {n.id for n in devoured}


def test_accept_subset_writes_only_those(prey, vault):
    a = analyze(prey)
    written = consume(vault, a, [1, 3], say=lambda s: None)
    assert len(written) == 3  # two memories + the meal episode
    assert {n.content for n in written[:2]} == {a.candidates[0].content, a.candidates[2].content}


def test_devoured_file_is_not_proposed_twice(prey, vault):
    consume(vault, analyze(prey), None, say=lambda s: None)
    again = analyze(prey, existing_source_hashes(vault))
    assert again.candidates == []
    assert again.already_devoured == 3  # README, notes, app.py — huge.md is size-skipped before it is ever hashed
    (prey / "README.md").write_text("# Salon Ops\n\nChanged.\n", encoding="utf-8")
    changed = analyze(prey, existing_source_hashes(vault))
    assert [c.where for c in changed.candidates] == ["README.md:1"]


def test_parse_accept():
    assert parse_accept(None, 5) is None
    assert parse_accept("all", 5) is None
    assert parse_accept("1,3,5", 5) == [1, 3, 5]
    assert parse_accept("2-4", 5) == [2, 3, 4]
    with pytest.raises(ValueError):
        parse_accept("9", 5)


def test_max_files_truncates(prey):
    a = analyze(prey, max_files=1)
    assert a.truncated and a.files_read == 1


def test_missing_path_is_an_error(vault):
    result = CliRunner().invoke(app, ["devour", "/no/such/place", "--vault", str(vault)])
    assert result.exit_code == 1
