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
