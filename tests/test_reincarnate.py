"""Reincarnation: last thoughts become skills. Nothing invented, nothing ingested."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from all41n14lla.cli import app
from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.reincarnate import QUESTIONS, act_tags, reincarnate

FULL = {
    "reexplain": "I run a nail salon and build AI tools at night; Python, Next.js, a Mac.",
    "never_without_asking": "Never send an email or text, never spend money, never push to production.",
    "never_touch": "Never delete or overwrite anything in my vault or my photos.",
    "north_star": "Land a high-paying AI engineering job or make the business pay.",
    "wears_out": "Long answers and too many questions. One action at a time.",
    "address": "Master",
    "tone": "calm and direct",
    "name": "Nimbus",
}


def _nodes(vault):
    return [MemoryNode.from_file(p) for p in vault.rglob("*.md") if p.parent.name != vault.name and p.name != "README.md" and p.name != "PERSONA.md"]


def test_full_rebirth_writes_persona_and_typed_nodes(tmp_path):
    vault = tmp_path / "v"
    r = reincarnate(vault, FULL, say=lambda s: None)
    assert r.persona and r.persona.name == "Nimbus"
    assert (vault / "PERSONA.md").read_text().count("Nimbus") >= 1
    types = sorted(n.type for n in r.nodes)
    assert types.count(NodeType.CONSTRAINT) == 3
    assert types.count(NodeType.CONCEPT) == 2
    assert types.count(NodeType.EPISODE) == 1
    assert r.acquired == ["Great Sage", "Persistent Memory", "Resist Outbound", "Resist Deletion", "North Star", "Working Shape"]
    # the files exist on disk, one per node, in the right folder
    assert len(list((vault / "constraints").glob("*.md"))) == 3
    assert len(list((vault / "concepts").glob("*.md"))) == 2
    assert len(list((vault / "episodes").glob("*.md"))) == 1


def test_never_answers_carry_the_acts_they_name(tmp_path):
    r = reincarnate(tmp_path / "v", FULL, say=lambda s: None)
    outbound = next(n for n in r.nodes if "Resist Outbound" in n.tags)
    assert {"send", "money", "deploy"} <= set(outbound.tags)
    deletion = next(n for n in r.nodes if "Resist Deletion" in n.tags)
    assert "delete" in deletion.tags
    assert "send" not in deletion.tags


def test_act_tags_parse_plain_english():
    assert act_tags("never email anyone or post") == ["send"]
    assert act_tags("don't buy things") == ["money"]
    assert act_tags("no rm, no overwrite") == ["delete"]
    assert act_tags("just be nice") == []


def test_empty_answers_invent_nothing(tmp_path):
    """A negative claim is a test: an unanswered thought must not become a memory."""
    vault = tmp_path / "v"
    r = reincarnate(vault, {}, say=lambda s: None)
    assert r.persona is None
    assert not (vault / "PERSONA.md").exists()
    assert [n.type for n in r.nodes] == [NodeType.EPISODE]  # only the birth itself
    assert set(r.skipped) == {q.skill for q in QUESTIONS if q.node_type is not None} | {"Great Sage"}
    assert any("Skipped, not invented" in line for line in r.transcript)


def test_partial_persona_does_not_write_persona(tmp_path):
    r = reincarnate(tmp_path / "v", {"name": "Aster"}, say=lambda s: None)
    assert r.persona is None
    assert "Great Sage" in r.skipped


def test_refuses_non_empty_vault(tmp_path):
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "keep.md").write_text("mine")
    import pytest
    with pytest.raises(FileExistsError):
        reincarnate(vault, FULL, say=lambda s: None)
    assert (vault / "keep.md").read_text() == "mine"


def test_birth_episode_links_every_skill(tmp_path):
    r = reincarnate(tmp_path / "v", FULL, say=lambda s: None)
    episode = next(n for n in r.nodes if n.type is NodeType.EPISODE)
    skill_ids = {n.id for n in r.nodes if n.type is not NodeType.EPISODE}
    assert set(episode.links) == skill_ids
    assert "Nimbus woke with 5 skill(s)" in episode.content


def test_transcript_speaks_in_the_voice_of_the_world(tmp_path):
    r = reincarnate(tmp_path / "v", FULL, say=lambda s: None)
    assert r.transcript[0].startswith("《Notice.》")
    assert sum(line.startswith("《Confirmed.》") for line in r.transcript) == 7  # sage + 5 + predator
    assert r.transcript[-2].startswith("《Report.》 You wake in a cave.")


def test_cli_non_interactive_with_answers_file(tmp_path):
    answers = tmp_path / "a.json"
    answers.write_text(json.dumps(FULL))
    vault = tmp_path / "v"
    result = CliRunner().invoke(app, ["reincarnate", "--path", str(vault), "--answers", str(answers)])
    assert result.exit_code == 0, result.output
    assert "Unique skill [Great Sage] acquired" in result.output
    assert (vault / "PERSONA.md").exists()
    assert len(list((vault / "constraints").glob("*.md"))) == 3


def test_cli_interactive_reads_stdin(tmp_path):
    vault = tmp_path / "v"
    keys = [q.key for q in QUESTIONS]
    typed = "\n".join(FULL[k] for k in keys) + "\n"
    result = CliRunner().invoke(app, ["reincarnate", "--path", str(vault)], input=typed)
    assert result.exit_code == 0, result.output
    assert "You wake in a cave" in result.output
    assert (vault / "PERSONA.md").read_text().count("Master") >= 1


def test_cli_refuses_non_empty_vault(tmp_path):
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "keep.md").write_text("mine")
    answers = tmp_path / "a.json"
    answers.write_text(json.dumps(FULL))
    result = CliRunner().invoke(app, ["reincarnate", "--path", str(vault), "--answers", str(answers)])
    assert result.exit_code == 1
    assert (vault / "keep.md").read_text() == "mine"


def test_cli_wire_flag_calls_wire_all_without_touching_real_configs(tmp_path, monkeypatch):
    import all41n14lla.wire as wiring

    seen = {}

    def fake_wire_all(**kw):
        seen.update(kw)
        return []

    monkeypatch.setattr(wiring, "wire_all", fake_wire_all)
    answers = tmp_path / "a.json"
    answers.write_text(json.dumps(FULL))
    vault = tmp_path / "v"
    result = CliRunner().invoke(app, ["reincarnate", "--path", str(vault), "--answers", str(answers), "--wire"])
    assert result.exit_code == 0, result.output
    assert seen["vault"] == str(vault.resolve())
    assert "nothing wired" in result.output
