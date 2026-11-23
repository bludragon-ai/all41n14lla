"""Smoke tests for the Typer CLI."""
from __future__ import annotations

from typer.testing import CliRunner

from all41n14lla.cli import app


def test_help_exits_zero():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_default_vault_honors_env(monkeypatch, tmp_path):
    """CLI default vault follows $ALL41N14LLA_VAULT, matching the MCP server."""
    monkeypatch.setenv("ALL41N14LLA_VAULT", str(tmp_path))
    from all41n14lla.cli import _default_vault

    assert _default_vault() == tmp_path


def test_default_vault_falls_back_to_dotfile(monkeypatch):
    """Without the env var, the CLI default is the ~/.all41n14lla dotfile."""
    monkeypatch.delenv("ALL41N14LLA_VAULT", raising=False)
    from pathlib import Path

    from all41n14lla.cli import _default_vault

    assert _default_vault() == Path.home() / ".all41n14lla"


def test_init_without_persona_flags_skips_persona(tmp_path):
    runner = CliRunner()
    target = tmp_path / "vault"
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 0
    assert not (target / "PERSONA.md").exists()


def test_init_with_persona_flags_writes_persona(tmp_path):
    runner = CliRunner()
    target = tmp_path / "vault"
    result = runner.invoke(
        app,
        ["init", "--path", str(target), "--name", "Aster", "--address", "Captain", "--tone", "direct"],
    )
    assert result.exit_code == 0
    persona_md = (target / "PERSONA.md").read_text()
    assert "Aster" in persona_md
    assert "Captain" in persona_md


def test_init_with_partial_persona_flags_errors(tmp_path):
    runner = CliRunner()
    target = tmp_path / "vault"
    result = runner.invoke(app, ["init", "--path", str(target), "--name", "Aster"])
    assert result.exit_code != 0
    assert not target.exists() or not any(target.iterdir())


def test_persona_command_reports_none_when_unset(tmp_path):
    runner = CliRunner()
    target = tmp_path / "vault"
    runner.invoke(app, ["init", "--path", str(target)])
    result = runner.invoke(app, ["persona", "--vault", str(target)])
    assert result.exit_code != 0


def test_persona_command_prints_persona_when_set(tmp_path):
    runner = CliRunner()
    target = tmp_path / "vault"
    runner.invoke(
        app,
        ["init", "--path", str(target), "--name", "Aster", "--address", "Captain", "--tone", "direct"],
    )
    result = runner.invoke(app, ["persona", "--vault", str(target)])
    assert result.exit_code == 0
    assert "Aster" in result.output
