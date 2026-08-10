"""FTS5 search over the nodes index.

Returns ranked (MemoryNode, score) pairs. The score is the negated BM25
output so higher numbers are better matches (SQLite's bm25() returns
lower-is-better by convention).
"""
from __future__ import annotations

from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import Storage


def _sanitize(query: str) -> str:
    """Quote each term as its own FTS5 phrase, joined by ``OR`` (recall-oriented).

    Quoting neutralizes FTS5 query operators (``AND``/``OR``/``NOT``/``NEAR``,
    ``-``, ``:``, ``*``, parentheses) so user text can never inject query
    syntax. Joining the quoted terms with ``OR`` makes a node matching ANY
    query term a candidate; BM25 then ranks nodes that match more (and rarer)
    terms higher, so a note containing every term still sorts to the top while
    a note matching only some still surfaces below it.

    This is the right default for a tool named ``recall``: a multi-word query
    is a description, not a phrase. The earlier implementation joined terms
    with FTS5's implicit AND (every term required in one note), which silently
    returned ``[]`` for natural recall queries whose words are spread across
    different notes — e.g. ``recall "Jordan career professional"`` never
    surfaced the professional-identity concept because no single note held all
    three words. (An even earlier version required the terms to be ADJACENT.)
    OR + BM25 ranking fixes both; single-term queries are unaffected (one term,
    no ``OR``).

    Terms with no alphanumeric characters tokenize to nothing (an empty FTS5
    phrase is a syntax error), so they are dropped.
    """
    terms = []
    for raw in query.split():
        term = raw.replace('"', "")
        if any(ch.isalnum() for ch in term):
            terms.append(f'"{term}"')
    return " OR ".join(terms)


def search(
    storage: Storage,
    query: str,
    node_type: NodeType | None = None,
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
            ORDER BY score ASC, n.updated DESC
            LIMIT ?
        """
        params: tuple = (q, node_type.value, limit)
    else:
        sql = """
            SELECT n.id, n.path, bm25(nodes_fts) AS score
            FROM nodes_fts
            JOIN nodes n ON n.id = nodes_fts.id
            WHERE nodes_fts MATCH ?
            ORDER BY score ASC, n.updated DESC
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
