"""Per-type retrieval policies — the deterministic constraint floor + typed rescoring.

This module implements the retrieval contract the README promises:

- **Constraints** whose tags overlap the query are ALWAYS returned. They are
  fetched on a separate, uncapped code path (the "constraint floor") keyed on
  tag overlap — a deterministic guarantee, not a ranking. A weak lexical match
  cannot drop a hard rule, by construction. Floor items are returned in the
  top ordinal slots so even a caller that only reads the first few results
  sees the rule. Constraints never decay.
- **Concepts** rank by lexical score plus a tag-overlap bonus.
- **Patterns** add a moderate recency boost (90-day half-life, floored so old
  playbooks are dampened, never erased).
- **Episodes** add a strong temporal decay (30-day half-life) — recent events
  outrank stale ones at equal relevance.

The precondition, stated out loud: the floor fires only when query terms
overlap a constraint's tags (stem-aware via the index's Porter tokenizer).
An untagged constraint, or a query with no overlapping terms, does not
trigger it. ``doctor`` reports untagged constraints for exactly this reason.

The floor carries a safety cap (``FLOOR_CAP``) so one hot tag cannot blow out
the caller's context window; when the cap trims matches the result's
``floor_overflow`` flag is set so the caller knows the floor was truncated.

Everything here is pure stdlib math over the existing SQLite index —
offline, deterministic, $0 per call.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.search import search as fts_search
from all41n14lla.engine.storage import Storage

# ── tuning knobs ─────────────────────────────────────────────────────────────
FLOOR_CAP = 50                # max constraints the floor injects (context-window guard)
LEXICAL_POOL = 200            # candidate pool fetched before rescoring
TAG_BONUS_PER_OVERLAP = 0.25  # multiplicative bonus per overlapping tag (capped at 2)
EPISODE_HALF_LIFE_DAYS = 30.0  # strong decay — the 30-day half-life recipe
PATTERN_HALF_LIFE_DAYS = 90.0  # moderate recency for playbooks
PATTERN_RECENCY_FLOOR = 0.6   # patterns are dampened by age, never erased

# Mirrors FTS5's unicode61-family tokenization: split on non-alphanumeric,
# keep single-char tokens ("c++" → "c", "r" → "r") so short/symbol tags can
# still trigger the floor exactly as the index sees them.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievalResult:
    """Ranked retrieval output: floor items first, then rescored lexical hits."""

    results: list[tuple[MemoryNode, float]] = field(default_factory=list)
    floor_ids: set[str] = field(default_factory=set)
    floor_overflow: bool = False


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _age_days(node: MemoryNode, now: datetime) -> float:
    """Age in days from ``created``, preferring file mtime when ``created`` is
    absent from the frontmatter.

    ``nodes._parse_dt`` silently defaults a missing ``created`` to *now*, which
    would make an old hand-written file masquerade as fresh. Detect that case
    (parse-time "now" on a file whose mtime is meaningfully older) and fall
    back to the mtime.
    """
    created = node.created
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    if node.path is not None:
        try:
            mtime = datetime.fromtimestamp(
                Path(node.path).stat().st_mtime, tz=UTC
            )
            fresh_created = created > now - timedelta(seconds=120)
            much_older_file = mtime < created - timedelta(seconds=120)
            if fresh_created and much_older_file:
                created = mtime
        except OSError:
            pass
    return max(0.0, (now - created).total_seconds() / 86400.0)


def _decay(age_days: float, half_life_days: float) -> float:
    """Exponential decay: 1.0 at age 0, 0.5 at one half-life. Pure math, $0."""
    return math.exp(-math.log(2.0) * age_days / half_life_days)


def _tag_overlap(node: MemoryNode, query_tokens: set[str]) -> int:
    node_tokens: set[str] = set()
    for tag in node.tags:
        node_tokens |= _tokenize(str(tag))
    return len(node_tokens & query_tokens)


def _rescore(
    node: MemoryNode, score: float, query_tokens: set[str], now: datetime
) -> float:
    """Apply the per-type policy to a lexical BM25 score (higher = better)."""
    bonus = 1.0 + TAG_BONUS_PER_OVERLAP * min(_tag_overlap(node, query_tokens), 2)
    if node.type is NodeType.EPISODE:
        return score * bonus * _decay(_age_days(node, now), EPISODE_HALF_LIFE_DAYS)
    if node.type is NodeType.PATTERN:
        recency = _decay(_age_days(node, now), PATTERN_HALF_LIFE_DAYS)
        return score * bonus * (
            PATTERN_RECENCY_FLOOR + (1.0 - PATTERN_RECENCY_FLOOR) * recency
        )
    # concepts (and any lexically-matched constraints) — no time penalty
    return score * bonus


def _constraint_floor(
    storage: Storage, query_tokens: set[str]
) -> tuple[list[tuple[MemoryNode, float]], bool]:
    """Fetch ALL constraints whose tags overlap the query tokens.

    Separate, uncapped (up to ``FLOOR_CAP``) code path: a column-scoped FTS
    MATCH on the ``tags`` column, restricted to ``type = 'constraint'``, with
    no lexical-rank cutoff. Returns ``(items, overflow)``.
    """
    if not query_tokens:
        return [], False
    terms = " OR ".join(f'"{t}"' for t in sorted(query_tokens))
    match = f"tags : ({terms})"
    rows = storage.conn.execute(
        """
        SELECT n.id, n.path, bm25(nodes_fts) AS score
        FROM nodes_fts
        JOIN nodes n ON n.id = nodes_fts.id
        WHERE nodes_fts MATCH ? AND n.type = ?
        ORDER BY score ASC, n.updated DESC
        """,
        (match, NodeType.CONSTRAINT.value),
    ).fetchall()
    items: list[tuple[MemoryNode, float]] = []
    for row in rows:
        path = Path(row["path"])
        if not path.exists():
            continue
        items.append((MemoryNode.from_file(path), -float(row["score"])))
    # Within the floor, more overlapping tags = more relevant rule. Keeps the
    # permissive any-overlap contract while stopping generic single-tag rules
    # from dominating the top slots.
    items.sort(
        key=lambda pair: (_tag_overlap(pair[0], query_tokens), pair[1]),
        reverse=True,
    )
    overflow = len(items) > FLOOR_CAP
    return items[:FLOOR_CAP], overflow


def retrieve(
    storage: Storage,
    query: str,
    node_type: NodeType | None = None,
    limit: int = 10,
    now: datetime | None = None,
) -> RetrievalResult:
    """Type-aware retrieval: constraint floor first, then rescored lexical hits.

    ``limit`` caps the *lexical* results; floor constraints are exempt from the
    cutoff and occupy the top ordinal slots (so a caller reading only the first
    result still sees the rule). When ``node_type`` restricts the search to a
    non-constraint type, the caller has explicitly scoped the recall and the
    floor is not injected.
    """
    now = now or datetime.now(UTC)
    query_tokens = _tokenize(query)

    floor: list[tuple[MemoryNode, float]] = []
    overflow = False
    if node_type in (None, NodeType.CONSTRAINT):
        floor, overflow = _constraint_floor(storage, query_tokens)

    lexical = fts_search(storage, query, node_type=node_type, limit=LEXICAL_POOL)
    rescored = sorted(
        (
            (node, _rescore(node, score, query_tokens, now))
            for node, score in lexical
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )

    floor_ids = {node.id for node, _ in floor}
    merged = list(floor)
    for node, score in rescored:
        if len(merged) >= len(floor) + limit:
            break
        if node.id in floor_ids:
            continue  # dedupe — the floor copy already holds the top slot
        merged.append((node, score))

    return RetrievalResult(results=merged, floor_ids=floor_ids, floor_overflow=overflow)
