"""Regression: the MCP server must actually SPEAK MCP over stdio.

Guard against the mcp 2.x breakage (mcp.server.fastmcp was removed in 2.x;
the pinned `mcp>=0.9.0,<2.0.0` keeps the 1.x FastMCP API). Importing the
module alone only proves the API surface exists; this exercises the real
public interface every harness connects to: spawn `serve`, do a JSON-RPC
initialize + tools/list round trip over stdin/stdout, and assert the
protocol handshake answers with the expected serverInfo and tool surface.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _spawn_server() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "all41n14lla", "serve"],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _send(proc: subprocess.Popen[str], msg: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def _recv(proc: subprocess.Popen[str]) -> dict:
    assert proc.stdout is not None
    line = proc.stdout.readline().strip()
    assert line, "server exited without answering"
    return json.loads(line)


def _close(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None:
        proc.stdin.close()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_initialize_handshake_answers_with_server_info() -> None:
    proc = _spawn_server()
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "jcode-smoke", "version": "1.0"},
                },
            },
        )
        resp = _recv(proc)
    finally:
        _close(proc)
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "all41n14lla"
    assert "tools" in result["capabilities"]


def test_tools_list_round_trip() -> None:
    proc = _spawn_server()
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "jcode-smoke", "version": "1.0"},
                },
            },
        )
        _recv(proc)
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        resp = _recv(proc)
    finally:
        _close(proc)
    assert resp["id"] == 2
    tools = {t["name"] for t in resp["result"]["tools"]}
    assert tools == {
        "remember", "recall", "inspect", "forget", "consolidate",
        "identity", "guard_output",
    }
