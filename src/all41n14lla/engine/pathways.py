"""Co-occurrence linking + pattern promotion — the ``consolidate`` engine (v0.2).

``consolidate`` is the one explicit maintenance pass over the brain. It:

1. **Scans** every node on disk (concepts, patterns, episodes, constraints).
2. **Rebuilds the tag co-occurrence graph** in the SQLite ``edges`` table — for
   every pair of nodes that share at least one *semantic* tag, the edge weight is
   set to the number of shared tags. ``inspect`` already reads this table, so
   populating it is all that's needed for real neighbor data.
3. **Decays** edges that are no longer reinforced — any pre-existing edge whose
   pair did *not* re-occur this run is multiplied by ``DECAY_FACTOR`` for every
   ``DECAY_PERIOD_DAYS`` since it was last seen. Decayed edges are reduced, never
   deleted (per spec); only *orphan* edges (an endpoint node that no longer
   exists) are pruned, since nothing else cleans them up (no FK cascade).
4. **Promotes** high-co-occurrence **concept** pairs into new ``pattern`` nodes —
   if two concepts share ``>= threshold`` tags and no existing pattern already
   links them, a draft pattern is minted documenting the overlap, flagged for
   review. Existing nodes are never modified or deleted.

Storage note
------------
The ``edges`` table is shared with the dormant episode-``links`` co-occurrence
signal (``Storage.increment_edges``). v0.2 treats ``edges`` as the *tag* graph and
SETs weights from the current tag snapshot, which overwrites any links-derived
weight for the same pair. The live brain has zero episode links, so this is inert
today.
# ponytail: tag-graph owns `edges`. If episode-links co-occurrence is ever
# populated, add an `edges.source` column to keep the two graphs separate.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import Storage, folder_for

# ── tuning knobs ──────────────────────────────────────────────────────────────
PROMOTE_THRESHOLD = 3.0      # min shared-tag weight for a concept pair to promote
DECAY_FACTOR = 0.9           # multiply a stale edge's weight by this …
DECAY_PERIOD_DAYS = 30.0     # … for every period of this many days since last seen

# Provenance markers on auto-minted patterns. Excluded from co-occurrence so the
# markers never create edges between auto-patterns (which would feed back into
# the next run). `unreviewed` doubles as the spec's `reviewed: false` flag, since
# the Node model has a fixed frontmatter schema and would drop a custom key.
AUTO_TAGS = ("auto-generated", "consolidate", "unreviewed")
_AUTO_TAG_SET = frozenset(AUTO_TAGS)

Pair = tuple[str, str]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_days(updated: str, now: datetime) -> float:
    """Days between an edge's ``updated`` iso timestamp and ``now`` (>= 0)."""
    try:
        ts = datetime.fromisoformat(updated)
    except (TypeError, ValueError):
        return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 86400.0)


def decay_multiplier(age_days: float, factor: float = DECAY_FACTOR,
                     period_days: float = DECAY_PERIOD_DAYS) -> float:
    """``factor ** (age_days / period_days)`` — 1.0 at age 0, ``factor`` at one period."""
    if age_days <= 0:
        return 1.0
    return factor ** (age_days / period_days)


def _semantic_tags(node: MemoryNode) -> set[str]:
    """Lower-cased, de-duped tags that count for co-occurrence (provenance excluded)."""
    out: set[str] = set()
    for raw in node.tags:
        if not raw:
            continue
        tag = str(raw).strip().lower()
        if tag and tag not in _AUTO_TAG_SET:
            out.add(tag)
    return out


def _is_auto_generated(node: MemoryNode) -> bool:
    """True for patterns consolidate itself minted — derived artifacts.

    They carry their sources' tags, so letting them back into co-occurrence would
    bind them to their own source concepts and never reach a fixed point. They are
    outputs of the graph, not inputs.
    """
    return any(str(t).strip().lower() == "auto-generated" for t in node.tags)


def _preview(node: MemoryNode, length: int = 80) -> str:
    """First non-blank line of the body, truncated — matches recall/inspect previews."""
    for line in node.content.strip().splitlines():
        line = line.strip()
        if line:
            return line[:length]
    return ""


def scan_nodes(vault: Path) -> dict[str, MemoryNode]:
    """Load every node on disk, keyed by id. Read-only."""
    nodes: dict[str, MemoryNode] = {}
    for nt in NodeType:
        folder = vault / folder_for(nt)
        if not folder.exists():
            continue
        for md_file in folder.glob("*.md"):
            try:
                node = MemoryNode.from_file(md_file)
            except Exception:
                continue
            nodes[node.id] = node
    return nodes


def tag_cooccurrence(
    nodes: dict[str, MemoryNode],
) -> tuple[dict[Pair, float], dict[Pair, set[str]]]:
    """Pairwise shared-tag weights across all nodes.

    Returns ``(weights, shared_tags)`` where each key is a canonical-ordered
    ``(min_id, max_id)`` pair, the weight is the count of tags the two share, and
    ``shared_tags`` lists which tags.
    """
    tag_to_ids: dict[str, list[str]] = defaultdict(list)
    for node in nodes.values():
        if _is_auto_generated(node):
            continue  # derived artifact — never an input to the graph
        for tag in _semantic_tags(node):
            tag_to_ids[tag].append(node.id)

    weights: dict[Pair, float] = defaultdict(float)
    shared: dict[Pair, set[str]] = defaultdict(set)
    for tag, ids in tag_to_ids.items():
        for a, b in combinations(sorted(set(ids)), 2):
            weights[(a, b)] += 1.0
            shared[(a, b)].add(tag)
    return weights, shared


def _pattern_body(a: MemoryNode, b: MemoryNode, weight: float, shared: set[str]) -> str:
    shared_str = ", ".join(sorted(shared)) if shared else "(none)"
    return (
        f"Auto-generated by `consolidate` (v0.2). These two concepts co-occur on "
        f"{int(weight)} shared tag(s) — weight {weight:.1f}.\n\n"
        f"Shared tags: {shared_str}\n\n"
        f"Source concepts (see `links` in the frontmatter):\n"
        f"- {a.id}\n  {_preview(a)}\n"
        f"- {b.id}\n  {_preview(b)}\n\n"
        f"---\n"
        f"This is a DRAFT. Review what these concepts genuinely share, rewrite "
        f"this body to capture the pattern, then remove the `unreviewed` tag. "
        f"To reject it, `forget` this node by the id in its frontmatter."
    )


def _already_promoted_pairs(nodes: dict[str, MemoryNode]) -> set[Pair]:
    """Concept pairs already covered by some existing pattern's ``links``."""
    covered: set[Pair] = set()
    for node in nodes.values():
        if node.type is NodeType.PATTERN and len(node.links) >= 2:
            ids = sorted(set(str(link) for link in node.links))
            for a, b in combinations(ids, 2):
                covered.add((a, b))
    return covered


def consolidate(
    storage: Storage,
    vault: Path,
    *,
    threshold: float = PROMOTE_THRESHOLD,
    promote: bool = True,
    dry_run: bool = False,
    now: Optional[datetime] = None,
) -> dict:
    """Rebuild the tag co-occurrence graph, decay stale edges, promote patterns.

    Args:
        storage: An *open* ``Storage`` (the caller owns the context manager).
        vault: Vault root holding the node folders.
        threshold: Minimum shared-tag weight for a concept pair to be promoted.
        promote: When False, only the edge graph is rebuilt/decayed (no patterns).
        dry_run: When True, nothing is written — the returned summary reports what
            *would* happen (edges, decay, and promotion candidates).
        now: Override the clock (tests/determinism). Defaults to UTC now.

    Returns a summary dict — see ``candidates``/``promotions`` for the detail rows.
    Never modifies or deletes an existing node; only adds new pattern nodes.

    Pattern minting is at-least-once: a crash between writing a pattern file and
    indexing it would leave an orphan file, which the next run's ``reconcile``
    (run first) folds back into the index. No existing node is ever at risk.
    """
    now = now or _now()
    vault = Path(vault)

    # Index hygiene first so `inspect` (which reads the index) sees a consistent
    # world. reconcile reindexes disk and drops rows for vanished files; it does
    # not touch edges or rewrite frontmatter, so timestamps are preserved.
    indexed = 0
    if not dry_run:
        indexed, _removed = storage.reconcile(vault)

    nodes = scan_nodes(vault)
    # Orphan detection keys off files PRESENT on disk, not successfully-parsed
    # nodes — a hand-corrupted (unparseable) file must not look like a deleted
    # node and get its still-valid edges pruned.
    # Guard folder existence like scan_nodes()/reconcile() do: on Python 3.11,
    # Path.glob() on a missing directory raises FileNotFoundError.
    disk_ids: set[str] = set()
    for nt in NodeType:
        folder = vault / folder_for(nt)
        if folder.exists():
            disk_ids.update(md_file.stem for md_file in folder.glob("*.md"))
    by_type: dict[str, int] = {nt.value: 0 for nt in NodeType}
    for node in nodes.values():
        by_type[node.type.value] += 1

    weights, shared = tag_cooccurrence(nodes)
    current_pairs = set(weights)
    now_iso = now.isoformat()

    # Snapshot existing edges BEFORE we touch anything (for decay + orphan prune).
    existing = storage.conn.execute(
        "SELECT src_id, dst_id, weight, updated FROM edges"
    ).fetchall()

    # 1. SET current co-occurrence weights (idempotent rebuild).
    for (a, b), w in weights.items():
        if not dry_run:
            storage.conn.execute(
                """
                INSERT INTO edges (src_id, dst_id, weight, updated)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(src_id, dst_id) DO UPDATE SET
                    weight = excluded.weight,
                    updated = excluded.updated
                """,
                (a, b, w, now_iso),
            )
    edges_written = len(weights)

    # 2. Decay stale edges (still-valid pair, but no longer co-occurring) and
    #    prune orphans (an endpoint node no longer exists). Decay advances
    #    `updated` so it accrues run-to-run without double-counting a re-run.
    edges_decayed = 0
    edges_pruned = 0
    for row in existing:
        pair = (row["src_id"], row["dst_id"])
        is_orphan = pair[0] not in disk_ids or pair[1] not in disk_ids
        if is_orphan:
            if not dry_run:
                storage.conn.execute(
                    "DELETE FROM edges WHERE src_id = ? AND dst_id = ?", pair
                )
            edges_pruned += 1
            continue
        if pair in current_pairs:
            continue  # freshly set above
        age = _age_days(row["updated"], now)
        if age <= 0:
            continue
        new_weight = row["weight"] * decay_multiplier(age)
        if not dry_run:
            storage.conn.execute(
                "UPDATE edges SET weight = ?, updated = ? WHERE src_id = ? AND dst_id = ?",
                (new_weight, now_iso, pair[0], pair[1]),
            )
        edges_decayed += 1

    # Flush the edge graph as a unit before promotion. upsert_node (below)
    # commits internally, so committing here keeps a mid-promotion crash from
    # leaving the edge writes riding an uncommitted pattern transaction.
    if not dry_run:
        storage.conn.commit()

    # 3. Promote concept pairs at/above threshold that no pattern already links.
    already = _already_promoted_pairs(nodes)
    candidates: list[dict] = []
    promotions: list[dict] = []
    if promote:
        for (a, b), w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
            if w < threshold:
                continue
            na, nb = nodes.get(a), nodes.get(b)
            if na is None or nb is None:
                continue
            if na.type is not NodeType.CONCEPT or nb.type is not NodeType.CONCEPT:
                continue
            shared_tags = sorted(shared[(a, b)])
            is_covered = (a, b) in already
            candidates.append(
                {
                    "source_nodes": [a, b],
                    "weight": w,
                    "shared_tags": shared_tags,
                    "previews": [_preview(na), _preview(nb)],
                    "already_promoted": is_covered,
                }
            )
            if is_covered:
                continue
            # dry-run reports the would-mint pair via `candidates` (already_promoted
            # is False); it does NOT mint, so it adds nothing to `promotions`.
            if dry_run:
                continue
            pattern = MemoryNode(
                type=NodeType.PATTERN,
                content=_pattern_body(na, nb, w, set(shared_tags)),
                tags=[*AUTO_TAGS, *shared_tags],
                links=[a, b],
                created=now,
                updated=now,
            )
            target = vault / folder_for(NodeType.PATTERN) / f"{pattern.id}.md"
            if target.exists():  # impossible uuid4 collision — never clobber a node
                raise RuntimeError(f"refusing to overwrite existing file at {target}")
            pattern.write(target)
            storage.upsert_node(pattern)
            # The new pattern covers this pair from here on (idempotent re-runs).
            already.add((a, b))
            promotions.append(
                {
                    "id": pattern.id,
                    "source_nodes": [a, b],
                    "weight": w,
                    "shared_tags": shared_tags,
                    "preview": _preview(pattern),
                }
            )

    if not dry_run:
        storage.conn.commit()

    return {
        "nodes_scanned": len(nodes),
        "by_type": by_type,
        "indexed": indexed,
        "edges_written": edges_written,
        "edges_decayed": edges_decayed,
        "edges_pruned": edges_pruned,
        "threshold": threshold,
        "promote": promote,
        "dry_run": dry_run,
        "candidates": candidates,
        "promotions": promotions,
    }
