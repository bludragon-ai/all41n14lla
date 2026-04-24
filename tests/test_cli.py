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
