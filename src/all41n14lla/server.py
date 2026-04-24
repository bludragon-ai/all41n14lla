"""all41n14lla MCP server (stdio transport).

Exposes ``remember``, ``recall``, ``forget``, ``inspect``, and ``consolidate``
as MCP tools for any MCP-capable client (Claude Desktop, Claude Code, Cursor,
etc.).

Vault location
--------------
The environment variable ``ALL41N14LLA_VAULT``, if set, points at the vault
root. Otherwise the server falls back to ``~/.all41n14lla/`` (the hidden
dotfile created by ``all41n14lla init``).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.search import search as fts_search
from all41n14lla.engine.storage import (
    Storage,
    default_db_path,
    folder_for,
)

mcp = FastMCP("all41n14lla")


def _vault_path() -> Path:
    env = os.environ.get("ALL41N14LLA_VAULT")
    base = Path(env) if env else Path.home() / ".all41n14lla"
    return base.expanduser().resolve()


def _require_vault() -> Path:
    vault = _vault_path()
    if not vault.exists():
        raise RuntimeError(
            f"No vault at {vault}. Run `all41n14lla init` first, "
            "or set ALL41N14LLA_VAULT to an existing vault path."
        )
    return vault


def _resolve_node_type(name: Optional[str]) -> Optional[NodeType]:
    if not name:
        return None
    try:
        return NodeType(name.lower())
    except ValueError as exc:
        raise ValueError(
            f"Unknown type '{name}'. Must be one of: "
            "concept, pattern, episode, constraint."
        ) from exc


@mcp.tool()
def remember(
    type: str,
    content: str,
    tags: Optional[list[str]] = None,
    links: Optional[list[str]] = None,
) -> dict:
    """Save a memory for future recall.

    Use this whenever the user shares a fact, decision, playbook, observation,
    or rule that should persist across sessions. Memories are written to
    markdown files on the user's disk; the user can edit them by hand later
    and the index reconciles on next read.

    The ``type`` argument is required and determines retrieval behavior:

    - ``concept``: a stable idea or definition ("CQRS separates reads and writes")
    - ``pattern``: a repeated behavior or playbook ("run pytest before every commit")
    - ``episode``: a specific event that happened ("shipped v0.3 to staging on Tuesday")
    - ``constraint``: a hard rule the agent should always respect ("never commit secrets")

    Returns ``{id, type, path}``.
    """
    vault = _require_vault()
    nt = _resolve_node_type(type)
    if nt is None:
        raise ValueError("'type' is required — one of concept, pattern, episode, constraint")

    node = MemoryNode(
        type=nt,
        content=content,
        tags=list(tags or []),
        links=list(links or []),
    )
    file_path = vault / folder_for(nt) / f"{node.id}.md"
    node.write(file_path)
    with Storage(default_db_path(vault)) as storage:
        storage.upsert_node(node)
        if nt is NodeType.EPISODE and node.links:
            storage.increment_edges(list(node.links))
    return {"id": node.id, "type": nt.value, "path": str(file_path)}


@mcp.tool()
def recall(
    query: str,
    type: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Search stored memories by full-text query.

    Use this whenever you need to look up what the user previously remembered
    before answering. Treats the query as a phrase match across memory content
    and tags; ranks with BM25.

    Args:
        query: The phrase to search for.
        type: Optional. Restrict to one of concept, pattern, episode, constraint.
        limit: Maximum number of matches to return (default 10).

    Returns a list of ``{id, type, content, tags, links, path, score}`` dicts,
    ranked highest-score-first.
    """
    vault = _require_vault()
    nt = _resolve_node_type(type)
    with Storage(default_db_path(vault)) as storage:
        hits = fts_search(storage, query, node_type=nt, limit=limit)

    return [
        {
            "id": node.id,
            "type": node.type.value,
            "content": node.content,
            "tags": list(node.tags),
            "links": list(node.links),
            "path": str(node.path) if node.path else None,
            "score": score,
        }
        for node, score in hits
    ]


@mcp.tool()
def forget(id: str) -> dict:
    """Permanently delete a memory by id.

    Use this when the user explicitly asks to remove a specific remembered
    item. Deletes both the markdown file on disk and the index row. Accepts a
    full UUID or an unambiguous prefix (first 8+ characters).

    Returns ``{deleted: bool, id: str | null, reason: str | null}``. If the
    prefix matches multiple nodes, nothing is deleted and ``reason`` explains.
    """
    vault = _require_vault()
    with Storage(default_db_path(vault)) as storage:
        rows = storage.conn.execute(
            "SELECT id, path FROM nodes WHERE id LIKE ?", (f"{id}%",)
        ).fetchall()
        if not rows:
            return {"deleted": False, "id": None, "reason": f"no node matches '{id}'"}
        if len(rows) > 1:
            return {
                "deleted": False,
                "id": None,
                "reason": (
                    f"ambiguous — '{id}' matches {len(rows)} nodes; use the full id"
                ),
            }
        target_id = rows[0]["id"]
        target_path = Path(rows[0]["path"])
        storage.delete_node(target_id)
    if target_path.exists():
        target_path.unlink()
    return {"deleted": True, "id": target_id, "reason": None}


@mcp.tool()
def inspect(query_or_id: str) -> dict:
    """Look up a single memory plus its nearest co-occurrence neighbors.

    If the argument matches a node id (full UUID or unambiguous prefix),
    returns that node. Otherwise runs a search and returns the top match.
    Either way, includes the 10 most-weighted edge neighbors from the pathways
    graph.

    Use this when the user wants to explore what's around a specific memory
    rather than search broadly. Returns ``{node, neighbors}`` or
    ``{node: null, neighbors: [], error: <reason>}`` on miss.
    """
    vault = _require_vault()
    with Storage(default_db_path(vault)) as storage:
        rows = storage.conn.execute(
            "SELECT id, path FROM nodes WHERE id LIKE ?", (f"{query_or_id}%",)
        ).fetchall()

        node: Optional[MemoryNode] = None
        if len(rows) == 1:
            target_path = Path(rows[0]["path"])
            if not target_path.exists():
                return {"node": None, "neighbors": [], "error": "index row orphaned"}
            node = MemoryNode.from_file(target_path)
        else:
            hits = fts_search(storage, query_or_id, limit=1)
            if hits:
                node, _ = hits[0]

        if node is None:
            return {"node": None, "neighbors": [], "error": "no match"}

        edges = storage.conn.execute(
            """
            SELECT dst_id AS neighbor_id, weight FROM edges WHERE src_id = ?
            UNION
            SELECT src_id AS neighbor_id, weight FROM edges WHERE dst_id = ?
            ORDER BY weight DESC
            LIMIT 10
            """,
            (node.id, node.id),
        ).fetchall()

    return {
        "node": {
            "id": node.id,
            "type": node.type.value,
            "content": node.content,
            "tags": list(node.tags),
            "links": list(node.links),
        },
        "neighbors": [
            {"id": r["neighbor_id"], "weight": float(r["weight"])} for r in edges
        ],
    }


@mcp.tool()
def consolidate() -> dict:
    """Promote high-co-occurrence concepts into patterns and apply decay.

    v0.1 scaffold only. Real implementation ships in v0.2.0. Calling this now
    returns a stub status so clients can confirm the tool is wired.
    """
    return {
        "status": "pending_v0.2.0",
        "message": "Pattern promotion and decay land in v0.2.0.",
    }


def main() -> None:
    """Entry point for ``all41n14lla serve``.

    Starts a watchdog observer on the vault (if it exists) so hand-edits to
    markdown files land in the SQLite index live, then runs the MCP stdio
    server. Observer is stopped cleanly on shutdown.
    """
    from all41n14lla.watcher import start_observer

    vault = _vault_path()
    observer = start_observer(vault) if vault.exists() else None
    try:
        mcp.run()
    finally:
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)


if __name__ == "__main__":
    main()
