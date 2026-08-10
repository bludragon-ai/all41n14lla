"""Tests for ``all41n14lla wire`` — client detection + idempotent MCP wiring.

Every test runs against a fake home directory under ``tmp_path``; nothing
touches the real user configs. The contract under test:

- detection finds exactly the clients whose config dir/file exists
- ``--dry-run`` writes NOTHING
- wiring preserves every pre-existing key in the target config
- a second run is a no-op (``already-wired``)
- a differing entry is a conflict, never silently overwritten; ``--force``
  replaces it for JSON clients
- unparseable configs are skipped with an error and left byte-identical
- modified configs get a ``.all41n14lla.bak`` backup sibling
- the Codex TOML path appends a valid ``[mcp_servers.all41n14lla]`` table
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from all41n14lla.wire import (
    ALREADY,
    BACKUP_SUFFIX,
    CONFLICT,
    ERROR,
    WIRED,
    WOULD_WIRE,
    known_clients,
    server_block,
    wire_all,
)

CMD = "/fake/bin/all41n14lla"


@pytest.fixture()
def home(tmp_path: Path) -> Path:
    """A fake macOS home with all five clients present, with realistic content."""
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"other-server": {"command": "other"}}, "theme": "dark"}),
        encoding="utf-8",
    )
    (tmp_path / "Library" / "Application Support" / "Claude").mkdir(parents=True)
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "settings.json").write_text(
        json.dumps({"selectedAuthType": "oauth-personal"}), encoding="utf-8"
    )
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"\n', encoding="utf-8"
    )
    return tmp_path


def _snapshot(home: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(home)): p.read_bytes()
        for p in home.rglob("*")
        if p.is_file()
    }


# ── detection ────────────────────────────────────────────────────────────────

def test_detects_all_five_clients(home: Path):
    detected = [c.name for c in known_clients(home, platform="darwin") if c.detected]
    assert detected == ["Claude Code", "Claude Desktop", "Cursor", "Gemini CLI", "Codex CLI"]


def test_detects_nothing_in_empty_home(tmp_path: Path):
    assert wire_all(home=tmp_path, command=CMD, platform="darwin") == []


def test_claude_code_detection_requires_the_file(home: Path):
    (home / ".claude.json").unlink()  # fake fixture file, not a real config
    detected = [c.name for c in known_clients(home, platform="darwin") if c.detected]
    assert "Claude Code" not in detected


# ── dry run ──────────────────────────────────────────────────────────────────

def test_dry_run_writes_nothing(home: Path):
    before = _snapshot(home)
    results = wire_all(home=home, command=CMD, dry_run=True, platform="darwin")
    assert _snapshot(home) == before
    assert {r.status for r in results} == {WOULD_WIRE}
    assert len(results) == 5


# ── wiring ───────────────────────────────────────────────────────────────────

def test_wire_all_wires_every_detected_client(home: Path):
    results = wire_all(home=home, command=CMD, platform="darwin")
    assert {r.status for r in results} == {WIRED}

    block = server_block(CMD)
    for rel in (".claude.json", ".cursor/mcp.json", ".gemini/settings.json",
                "Library/Application Support/Claude/claude_desktop_config.json"):
        data = json.loads((home / rel).read_text(encoding="utf-8"))
        assert data["mcpServers"]["all41n14lla"] == block, rel

    codex = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert codex["mcp_servers"]["all41n14lla"] == {"command": CMD, "args": ["serve"]}


def test_wire_preserves_existing_config_content(home: Path):
    wire_all(home=home, command=CMD, platform="darwin")

    claude = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert claude["theme"] == "dark"
    assert claude["mcpServers"]["other-server"] == {"command": "other"}

    gemini = json.loads((home / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    assert gemini["selectedAuthType"] == "oauth-personal"

    codex = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert codex["model"] == "gpt-5"
    assert codex["mcp_servers"]["other"] == {"command": "other"}


def test_second_run_is_a_noop(home: Path):
    wire_all(home=home, command=CMD, platform="darwin")
    after_first = _snapshot(home)
    results = wire_all(home=home, command=CMD, platform="darwin")
    assert {r.status for r in results} == {ALREADY}
    assert _snapshot(home) == after_first


def test_vault_env_is_embedded(home: Path):
    wire_all(home=home, command=CMD, vault="/tmp/myvault", platform="darwin")
    data = json.loads((home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["all41n14lla"]["env"] == {
        "ALL41N14LLA_VAULT": "/tmp/myvault"
    }
    codex = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert codex["mcp_servers"]["all41n14lla"]["env"] == {
        "ALL41N14LLA_VAULT": "/tmp/myvault"
    }


# ── conflicts ────────────────────────────────────────────────────────────────

def test_differing_entry_is_conflict_not_overwrite(home: Path):
    wire_all(home=home, command=CMD, platform="darwin")
    results = wire_all(home=home, command="/different/bin", platform="darwin")
    assert {r.status for r in results} == {CONFLICT}
    # original wiring untouched
    data = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["all41n14lla"]["command"] == CMD


def test_force_replaces_json_conflict_but_not_toml(home: Path):
    wire_all(home=home, command=CMD, platform="darwin")
    results = {
        r.client: r for r in wire_all(
            home=home, command="/different/bin", force=True, platform="darwin"
        )
    }
    assert results["Claude Code"].status == WIRED
    assert results["Cursor"].status == WIRED
    assert results["Codex CLI"].status == CONFLICT  # no stdlib TOML writer
    data = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["all41n14lla"]["command"] == "/different/bin"


# ── safety ───────────────────────────────────────────────────────────────────

def test_broken_json_is_skipped_untouched(home: Path):
    (home / ".claude.json").write_text("{not json", encoding="utf-8")
    results = {r.client: r for r in wire_all(home=home, command=CMD, platform="darwin")}
    assert results["Claude Code"].status == ERROR
    assert (home / ".claude.json").read_text(encoding="utf-8") == "{not json"
    # the other clients still got wired
    assert results["Cursor"].status == WIRED


def test_broken_toml_is_skipped_untouched(home: Path):
    (home / ".codex" / "config.toml").write_text("model = ", encoding="utf-8")
    results = {r.client: r for r in wire_all(home=home, command=CMD, platform="darwin")}
    assert results["Codex CLI"].status == ERROR
    assert (home / ".codex" / "config.toml").read_text(encoding="utf-8") == "model = "


def test_non_object_mcp_servers_is_refused_not_clobbered(home: Path):
    # greptile P1 2026-08-10: mcpServers present but NOT an object must be
    # refused, never silently replaced with {} — the old code overwrote the
    # existing value, wrote the config, and reported success (data loss).
    original = '{"mcpServers": ["oops"], "theme": "dark"}'
    (home / ".claude.json").write_text(original, encoding="utf-8")
    results = {r.client: r for r in wire_all(home=home, command=CMD, platform="darwin")}
    assert results["Claude Code"].status == ERROR
    assert (home / ".claude.json").read_text(encoding="utf-8") == original
    assert not (home / (".claude.json" + BACKUP_SUFFIX)).exists()  # never wrote
    # the other clients still got wired
    assert results["Cursor"].status == WIRED


def test_backup_written_before_modification(home: Path):
    original = (home / ".claude.json").read_bytes()
    wire_all(home=home, command=CMD, platform="darwin")
    backup = home / (".claude.json" + BACKUP_SUFFIX)
    assert backup.exists()
    assert backup.read_bytes() == original


def test_missing_config_file_created_without_backup(home: Path):
    wire_all(home=home, command=CMD, platform="darwin")
    assert (home / ".cursor" / "mcp.json").exists()
    assert not (home / ".cursor" / ("mcp.json" + BACKUP_SUFFIX)).exists()


# ── CLI surface ──────────────────────────────────────────────────────────────

def test_cli_wire_dry_run(home: Path, monkeypatch):
    from typer.testing import CliRunner

    from all41n14lla.cli import app

    monkeypatch.setenv("HOME", str(home))  # Path.home() on POSIX
    monkeypatch.delenv("ALL41N14LLA_VAULT", raising=False)
    before = _snapshot(home)
    result = CliRunner().invoke(app, ["wire", "--dry-run", "--command", CMD])
    assert result.exit_code == 0, result.output
    assert _snapshot(home) == before
    assert "would wire" in result.output


def test_cli_wire_empty_home_friendly_message(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner

    from all41n14lla.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(app, ["wire", "--dry-run"])
    assert result.exit_code == 0
    assert "No known MCP clients detected" in result.output
