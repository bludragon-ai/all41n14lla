"""FTS5 search over the nodes index.

Returns ranked (MemoryNode, score) pairs. The score is the negated BM25
output so higher numbers are better matches (SQLite's bm25() returns
lower-is-better by convention).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import Storage


def _sanitize(query: str) -> str:
    """Wrap the query as an FTS5 phrase so special operators are neutralized."""
    cleaned = query.replace('"', "").strip()
    return f'"{cleaned}"' if cleaned else ""


def search(
    storage: Storage,
    query: str,
    node_type: Optional[NodeType] = None,
    limit: int = 10,
) -> list[tuple[MemoryNode, float]]:
    """Return (node, score) pairs ranked by FTS5 relevance. Higher score = better match."""
    q = _sanitize(query)
    if not q:
        return []
    if node_type is not None:
        sql = """
            SELECT n.id, n.path, bm25(nodes_fts) AS score
            FROM nodes_fts
            JOIN nodes n ON n.id = nodes_fts.id
            WHERE nodes_fts MATCH ? AND n.type = ?
            ORDER BY score ASC
            LIMIT ?
        """
        params: tuple = (q, node_type.value, limit)
    else:
        sql = """
            SELECT n.id, n.path, bm25(nodes_fts) AS score
            FROM nodes_fts
            JOIN nodes n ON n.id = nodes_fts.id
            WHERE nodes_fts MATCH ?
            ORDER BY score ASC
            LIMIT ?
        """
        params = (q, limit)
    rows = storage.conn.execute(sql, params).fetchall()
    results: list[tuple[MemoryNode, float]] = []
    for row in rows:
        path = Path(row["path"])
        if not path.exists():
            continue
        node = MemoryNode.from_file(path)
        results.append((node, -float(row["score"])))
    return results
