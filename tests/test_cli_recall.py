"""End-to-end CLI regression for the README "First run" block.

The install-friction audit (2026-06-10) found that the EXACT command sequence
documented in the README returned "No matches." because multi-word recall was
phrase-matched. This suite runs the documented flow verbatim through the
Typer CLI so the quickstart can never silently break again.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from all41n14lla.cli import app

README_NOTE = "sqlite fts5 uses the porter tokenizer by default"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.delenv("ALL41N14LLA_VAULT", raising=False)
    return tmp_path / "vault"


def test_readme_first_run_block(runner: CliRunner, vault: Path):
    """init → remember → recall, exactly as README.md documents it."""
    result = runner.invoke(app, ["init", "--path", str(vault)])
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app, ["remember", "concept", README_NOTE, "--vault", str(vault)]
    )
    assert result.exit_code == 0, result.output

    # the exact failing command from the audit: two non-adjacent terms
    result = runner.invoke(app, ["recall", "sqlite tokenizer", "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert "No matches" not in result.output, (
        "the README quickstart recall must return the remembered concept"
    )
    assert "concept" in result.output


def test_recall_single_word_still_works(runner: CliRunner, vault: Path):
    runner.invoke(app, ["init", "--path", str(vault)])
    runner.invoke(app, ["remember", "concept", README_NOTE, "--vault", str(vault)])

    result = runner.invoke(app, ["recall", "sqlite", "--vault", str(vault)])
    assert result.exit_code == 0
    assert "No matches" not in result.output


def test_recall_miss_still_reports_no_matches(runner: CliRunner, vault: Path):
    runner.invoke(app, ["init", "--path", str(vault)])
    runner.invoke(app, ["remember", "concept", README_NOTE, "--vault", str(vault)])

    result = runner.invoke(app, ["recall", "kubernetes ingress", "--vault", str(vault)])
    assert result.exit_code == 0
    assert "No matches" in result.output


def test_server_recall_tool_handles_multiword(tmp_path: Path, monkeypatch):
    """The MCP server's recall tool rides the same code path — prove it too."""
    from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path

    vault = tmp_path / "vault"
    for folder in NODE_FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    with Storage(default_db_path(vault)):
        pass
    monkeypatch.setenv("ALL41N14LLA_VAULT", str(vault))

    from all41n14lla.server import recall, remember

    remember(type="concept", content=README_NOTE)
    hits = recall(query="sqlite tokenizer")
    assert len(hits) == 1
    assert hits[0]["content"] == README_NOTE
