"""Evolve — a read-only report of what the assistant has become.

Sage → Great Sage → Wisdom King Raphael: in the story the skill evolves as it is used. Here the
tier is earned by episodes remembered, and the report says plainly what each tier is allowed to
do. Nothing here changes behaviour by itself — it is the mirror, not the dial. (The dial —
autonomy actually widening — is a later, separate, consented step.)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from all41n14lla.engine.nodes import NodeType
from all41n14lla.engine.storage import Storage, default_db_path

TIERS: tuple[tuple[int, str, str], ...] = (
    (0, "Sage", "answers what it is asked; every act is yours"),
    (10, "Great Sage", "drafts and stages on its own; sends, spends, deletes, deploys stay yours"),
    (100, "Wisdom King Raphael", "runs standing routines unasked and reports; the same four acts stay yours"),
)


def tier_for(episodes: int) -> tuple[str, str, int | None]:
    """(name, what it may do, episodes until the next tier or None at the top)."""
    name, allowed, nxt = TIERS[0][1], TIERS[0][2], TIERS[1][0]
    for i, (floor, n, a) in enumerate(TIERS):
        if episodes >= floor:
            name, allowed = n, a
            nxt = TIERS[i + 1][0] if i + 1 < len(TIERS) else None
    return name, allowed, (None if nxt is None else max(0, nxt - episodes))


@dataclass(frozen=True)
class Evolution:
    concepts: int
    patterns: int
    episodes: int
    constraints: int
    devoured: int
    tier: str
    allowed: str
    until_next: int | None


def evolution(vault: Path) -> Evolution:
    vault = vault.expanduser().resolve()
    with Storage(default_db_path(vault)) as storage:
        counts = {t: len(storage.list_nodes(t)) for t in NodeType}
    devoured = sum(1 for p in vault.rglob("*.md") if p.parent != vault and "source_hash:" in p.read_text(encoding="utf-8", errors="ignore")[:1200])
    tier, allowed, until = tier_for(counts[NodeType.EPISODE])
    return Evolution(
        concepts=counts[NodeType.CONCEPT], patterns=counts[NodeType.PATTERN],
        episodes=counts[NodeType.EPISODE], constraints=counts[NodeType.CONSTRAINT],
        devoured=devoured, tier=tier, allowed=allowed, until_next=until,
    )
