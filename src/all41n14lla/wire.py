"""Wire the all41n14lla MCP server into installed LLM clients.

``all41n14lla wire`` detects which MCP-capable clients are present on this
machine and adds the server block to each one's config file. Design goals:

- **Idempotent** — a client that is already wired with identical settings is
  reported and left untouched; running ``wire`` twice changes nothing.
- **Never destructive** — every config that is about to be modified is backed
  up next to the original first (``<name>.all41n14lla.bak``). An existing
  ``all41n14lla`` entry with *different* settings is reported as a conflict,
  not overwritten (pass ``--force`` to replace it — JSON clients only). A
  config that fails to parse is skipped with an error, never rewritten.
- **Previewable** — ``--dry-run`` reports exactly what would change and
  writes nothing.

Supported clients (detection rule → config file):

==============  ==============================================  ======
Client          Config file                                     Format
==============  ==============================================  ======
Claude Code     ``~/.claude.json``                              JSON, ``mcpServers`` key
Claude Desktop  ``~/Library/Application Support/Claude/claude_desktop_config.json``
                (macOS; ``%APPDATA%/Claude`` on Windows)        JSON, ``mcpServers`` key
Cursor          ``~/.cursor/mcp.json``                          JSON, ``mcpServers`` key
Gemini CLI      ``~/.gemini/settings.json``                     JSON, ``mcpServers`` key
Codex CLI       ``~/.codex/config.toml``                        TOML, ``[mcp_servers.all41n14lla]`` table
==============  ==============================================  ======

Claude Code is detected by its config *file* (the CLI creates it on first
run); the others are detected by their config *directory*, and the config
file is created if the directory exists but the file does not.

TOML note: Python's stdlib can read TOML (``tomllib``) but not write it, and
this project takes no new dependencies for a convenience command. Codex
wiring therefore APPENDS a ``[mcp_servers.all41n14lla]`` table to the end of
``config.toml`` (always syntactically valid for a table that does not already
exist) and validates the result with ``tomllib`` before writing. ``--force``
cannot rewrite an existing TOML entry — that one is reported for hand-editing.
"""
from __future__ import annotations

import json
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

SERVER_NAME = "all41n14lla"
BACKUP_SUFFIX = ".all41n14lla.bak"

# Result statuses
WIRED = "wired"
ALREADY = "already-wired"
WOULD_WIRE = "would-wire"
CONFLICT = "conflict"
ERROR = "error"


@dataclass
class WireResult:
    """Outcome of wiring one client."""

    client: str
    config: Path
    status: str
    detail: str = ""


@dataclass(frozen=True)
class Client:
    """One known MCP client: where its config lives and how it is shaped."""

    name: str
    config: Path
    kind: str  # "json" | "toml"
    detected: bool = field(default=False)


def server_block(command: str, vault: str | None = None) -> dict:
    """The MCP server entry we write: ``{command, args[, env]}``."""
    block: dict = {"command": command, "args": ["serve"]}
    if vault:
        block["env"] = {"ALL41N14LLA_VAULT": vault}
    return block


def resolve_command() -> str:
    """Absolute path to the installed binary, falling back to the bare name.

    GUI clients (Claude Desktop especially) launch MCP servers with a
    restricted PATH, so an absolute path avoids the #1 wiring failure.
    """
    return shutil.which(SERVER_NAME) or SERVER_NAME


def known_clients(home: Path, platform: str = sys.platform) -> list[Client]:
    """Every client this command knows about, with its detection result."""
    if platform == "darwin":
        desktop_dir = home / "Library" / "Application Support" / "Claude"
    elif platform.startswith("win"):
        desktop_dir = home / "AppData" / "Roaming" / "Claude"
    else:
        desktop_dir = home / ".config" / "Claude"

    claude_code = home / ".claude.json"
    return [
        Client("Claude Code", claude_code, "json", claude_code.exists()),
        Client(
            "Claude Desktop",
            desktop_dir / "claude_desktop_config.json",
            "json",
            desktop_dir.is_dir(),
        ),
        Client("Cursor", home / ".cursor" / "mcp.json", "json", (home / ".cursor").is_dir()),
        Client(
            "Gemini CLI",
            home / ".gemini" / "settings.json",
            "json",
            (home / ".gemini").is_dir(),
        ),
        Client(
            "Codex CLI",
            home / ".codex" / "config.toml",
            "toml",
            (home / ".codex").is_dir(),
        ),
    ]


def _backup(config: Path) -> None:
    """Copy the config aside before the first modifying write."""
    if config.exists():
        shutil.copy2(config, config.with_name(config.name + BACKUP_SUFFIX))


def _wire_json(client: Client, block: dict, dry_run: bool, force: bool) -> WireResult:
    data: dict = {}
    if client.config.exists():
        try:
            text = client.config.read_text(encoding="utf-8")
            data = json.loads(text) if text.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            return WireResult(client.name, client.config, ERROR, f"could not parse: {exc}")
        if not isinstance(data, dict):
            return WireResult(
                client.name, client.config, ERROR, "top-level JSON is not an object"
            )

    # Same shape discipline as the top level (greptile P1 2026-08-10): a
    # PRESENT but non-object mcpServers (including explicit null) is refused
    # rather than silently replaced with {} — the old code clobbered whatever
    # the user had written there and reported success, destroying config data
    # with no error.
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        return WireResult(
            client.name,
            client.config,
            ERROR,
            'mcpServers is not an object — refusing to overwrite it '
            "(fix or remove the value, then rerun)",
        )
    # A PRESENT entry is a conflict even when its value is null: servers.get()
    # collapses "missing" and "explicit null" to None, so the presence check
    # must use `in` to keep an explicit null from being silently replaced
    # (greptile P1 2026-08-10, same family as the section-level null above).
    present = SERVER_NAME in servers
    existing = servers.get(SERVER_NAME)
    if existing == block:
        return WireResult(client.name, client.config, ALREADY)
    if present and not force:
        return WireResult(
            client.name,
            client.config,
            CONFLICT,
            "an all41n14lla entry already exists with different settings — "
            "rerun with --force to replace it",
        )
    if dry_run:
        return WireResult(
            client.name, client.config, WOULD_WIRE, json.dumps({SERVER_NAME: block})
        )

    _backup(client.config)
    servers[SERVER_NAME] = block
    data["mcpServers"] = servers
    client.config.parent.mkdir(parents=True, exist_ok=True)
    client.config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return WireResult(client.name, client.config, WIRED)


def _toml_snippet(block: dict) -> str:
    """A ``[mcp_servers.all41n14lla]`` table as TOML text.

    ``json.dumps`` is used for string values: its escaping (backslash, quote,
    control characters, ``\\uXXXX``) is valid inside a TOML basic string.
    """
    lines = [
        f"[mcp_servers.{SERVER_NAME}]",
        f"command = {json.dumps(block['command'])}",
        'args = ["serve"]',
    ]
    env = block.get("env")
    if env:
        lines.append("")
        lines.append(f"[mcp_servers.{SERVER_NAME}.env]")
        for key, value in env.items():
            lines.append(f"{key} = {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def _wire_toml(client: Client, block: dict, dry_run: bool, force: bool) -> WireResult:
    existing_text = ""
    if client.config.exists():
        try:
            existing_text = client.config.read_text(encoding="utf-8")
            data = tomllib.loads(existing_text)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return WireResult(client.name, client.config, ERROR, f"could not parse: {exc}")
        existing = data.get("mcp_servers", {}).get(SERVER_NAME)
        if existing is not None:
            want = {k: v for k, v in block.items()}
            have = {k: existing[k] for k in ("command", "args", "env") if k in existing}
            if have == want:
                return WireResult(client.name, client.config, ALREADY)
            return WireResult(
                client.name,
                client.config,
                CONFLICT,
                "an all41n14lla entry already exists with different settings — "
                "stdlib cannot rewrite TOML in place; edit the file by hand"
                + (" (--force does not apply to TOML)" if force else ""),
            )

    snippet = _toml_snippet(block)
    if dry_run:
        return WireResult(client.name, client.config, WOULD_WIRE, snippet.strip())

    new_text = existing_text
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text:
        new_text += "\n"
    new_text += snippet
    try:
        tomllib.loads(new_text)  # belt and suspenders: never write invalid TOML
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover — defensive
        return WireResult(
            client.name, client.config, ERROR, f"refusing to write invalid TOML: {exc}"
        )

    _backup(client.config)
    client.config.parent.mkdir(parents=True, exist_ok=True)
    client.config.write_text(new_text, encoding="utf-8")
    return WireResult(client.name, client.config, WIRED)


def wire_all(
    home: Path | None = None,
    command: str | None = None,
    vault: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    platform: str = sys.platform,
) -> list[WireResult]:
    """Detect every known client under ``home`` and wire each detected one.

    Returns one :class:`WireResult` per *detected* client. Undetected clients
    are silently skipped — wiring a config for a tool that is not installed
    would just leave confusing litter in the user's home directory.
    """
    home = home or Path.home()
    block = server_block(command or resolve_command(), vault)
    results: list[WireResult] = []
    for client in known_clients(home, platform):
        if not client.detected:
            continue
        if client.kind == "toml":
            results.append(_wire_toml(client, block, dry_run, force))
        else:
            results.append(_wire_json(client, block, dry_run, force))
    return results
