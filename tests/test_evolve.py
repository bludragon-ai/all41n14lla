from __future__ import annotations

from typer.testing import CliRunner

from all41n14lla.cli import app
from all41n14lla.evolve import evolution, tier_for
from all41n14lla.reincarnate import reincarnate


def test_tiers():
    assert tier_for(0)[0] == "Sage" and tier_for(0)[2] == 10
    assert tier_for(9)[0] == "Sage"
    assert tier_for(10)[0] == "Great Sage" and tier_for(10)[2] == 90
    assert tier_for(100)[0] == "Wisdom King Raphael" and tier_for(100)[2] is None


def test_evolution_counts_a_newborn(tmp_path):
    v = tmp_path / "v"
    reincarnate(v, {"name": "N", "address": "A", "tone": "t", "north_star": "ship it"}, say=lambda s: None)
    e = evolution(v)
    assert (e.concepts, e.episodes, e.constraints, e.devoured) == (1, 1, 0, 0)
    assert e.tier == "Sage" and e.until_next == 9


def test_cli_evolve(tmp_path):
    v = tmp_path / "v"
    reincarnate(v, {"name": "N", "address": "A", "tone": "t"}, say=lambda s: None)
    result = CliRunner().invoke(app, ["evolve", "--vault", str(v)])
    assert result.exit_code == 0, result.output
    assert "Tier:" in result.output and "Sage" in result.output
