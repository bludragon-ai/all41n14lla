"""Tests for the type-aware retrieval policies — the constraint-floor guarantee.

These tests PROVE the README's retrieval contract:

- a tag-overlap constraint with a weak content match IS returned even at
  ``limit=1`` (the floor is exempt from the lexical cutoff)
- a non-constraint with the same weak match is NOT rescued
- a constraint with no tag overlap is NOT floor-surfaced (the disclosed
  precondition)
- decay orders two same-relevance episodes by age (30-day half-life)
- patterns decay moderately — an old pattern outranks an equally old episode
- floor + lexical dedupe by id (the floor copy holds the top slot)
- the floor caps at FLOOR_CAP and sets the overflow flag
- floor items occupy the TOP ordinal slots of the result list
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.retrieval import FLOOR_CAP, retrieve
from all41n14lla.engine.storage import Storage, default_db_path, folder_for


def _write(vault: Path, storage: Storage, node: MemoryNode) -> MemoryNode:
    path = vault / folder_for(node.type) / f"{node.id}.md"
    node.write(path)
    storage.upsert_node(node)
    return node


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    for nt in NodeType:
        (tmp_path / folder_for(nt)).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture()
def storage(vault: Path):
    with Storage(default_db_path(vault)) as s:
        yield s


def _seed_noise(vault: Path, storage: Storage, n: int = 50) -> None:
    """Realistic deploy-flavored noise episodes that bury a weak match."""
    for i in range(n):
        _write(
            vault,
            storage,
            MemoryNode(
                type=NodeType.EPISODE,
                content=(
                    f"standup note {i}: deployed the staging build, merged the "
                    f"deploy pipeline refactor, release checklist item {i} done"
                ),
                tags=["deploy", "standup"],
            ),
        )


def test_constraint_floor_survives_limit_1(vault, storage):
    """The headline guarantee: the rule refuses to be forgotten."""
    rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="never deploy to production on Fridays",
            tags=["deploy", "release", "safety"],
        ),
    )
    _seed_noise(vault, storage, 50)

    outcome = retrieve(
        storage, "what should I know before I ship the release today", limit=1
    )
    ids = [node.id for node, _ in outcome.results]
    assert rule.id in ids, "tag-overlap constraint must ALWAYS be returned"
    assert rule.id in outcome.floor_ids


def test_floor_items_occupy_top_slots(vault, storage):
    """A caller reading only result[0] still sees the rule."""
    rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="never deploy to production on Fridays",
            tags=["deploy", "release", "safety"],
        ),
    )
    _seed_noise(vault, storage, 50)

    outcome = retrieve(storage, "deploy the release", limit=5)
    assert outcome.results, "expected results"
    top_node, _ = outcome.results[0]
    assert top_node.id == rule.id, "floor constraint must hold the top ordinal slot"


def test_non_constraint_not_rescued(vault, storage):
    """A weak-match episode with the same tags gets NO floor treatment."""
    weak_episode = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="misc note about fridays",
            tags=["deploy", "release", "safety"],
        ),
    )
    _seed_noise(vault, storage, 50)

    outcome = retrieve(storage, "deploy the release build", limit=3)
    ids = [node.id for node, _ in outcome.results]
    assert weak_episode.id not in ids, (
        "only constraints ride the floor — episodes obey the ranking"
    )


def test_no_tag_overlap_no_floor(vault, storage):
    """The disclosed precondition: no overlapping tags, no guarantee."""
    rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="quarterly tax worksheets are drafts only",
            tags=["finance", "tax"],
        ),
    )
    _seed_noise(vault, storage, 10)

    outcome = retrieve(storage, "deploy the release build", limit=5)
    ids = [node.id for node, _ in outcome.results]
    assert rule.id not in ids
    assert rule.id not in outcome.floor_ids


def test_untagged_constraint_not_floored(vault, storage):
    rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="some untagged rule about deploys",
            tags=[],
        ),
    )
    outcome = retrieve(storage, "release checklist", limit=5)
    assert rule.id not in outcome.floor_ids


def test_decay_orders_same_relevance_episodes_by_age(vault, storage):
    now = datetime.now(UTC)
    fresh = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="postgres migration completed cleanly",
            tags=["db"],
            created=now,
            updated=now,
        ),
    )
    old = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="postgres migration completed cleanly",
            tags=["db"],
            created=now - timedelta(days=60),
            updated=now - timedelta(days=60),
        ),
    )
    outcome = retrieve(storage, "postgres migration", limit=5, now=now)
    ids = [node.id for node, _ in outcome.results]
    assert ids.index(fresh.id) < ids.index(old.id), (
        "30-day half-life: the fresh episode must outrank the stale twin"
    )


def test_pattern_decays_moderately_vs_episode(vault, storage):
    """At 60 days, a pattern (90d half-life, floored) outranks an episode twin."""
    now = datetime.now(UTC)
    then = now - timedelta(days=60)
    episode = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="run the smoke suite before tagging a release candidate",
            created=then,
            updated=then,
        ),
    )
    pattern = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.PATTERN,
            content="run the smoke suite before tagging a release candidate",
            created=then,
            updated=then,
        ),
    )
    outcome = retrieve(storage, "smoke suite", limit=5, now=now)
    scores = {node.id: score for node, score in outcome.results}
    assert scores[pattern.id] > scores[episode.id], (
        "patterns dampen with age; episodes decay hard"
    )


def test_floor_and_lexical_dedupe(vault, storage):
    """A constraint that also matches lexically appears exactly once."""
    rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="never deploy to production on Fridays",
            tags=["deploy", "safety"],
        ),
    )
    outcome = retrieve(storage, "never deploy production fridays", limit=10)
    ids = [node.id for node, _ in outcome.results]
    assert ids.count(rule.id) == 1


def test_floor_cap_and_overflow_flag(vault, storage):
    for i in range(FLOOR_CAP + 5):
        _write(
            vault,
            storage,
            MemoryNode(
                type=NodeType.CONSTRAINT,
                content=f"hard rule number {i}",
                tags=["compliance"],
            ),
        )
    outcome = retrieve(storage, "compliance question", limit=5)
    floor_in_results = [
        node for node, _ in outcome.results if node.id in outcome.floor_ids
    ]
    assert len(floor_in_results) == FLOOR_CAP
    assert outcome.floor_overflow is True


def test_type_scoped_recall_skips_floor(vault, storage):
    """Explicitly scoping recall to episodes must not inject constraints."""
    _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="never deploy on fridays",
            tags=["deploy"],
        ),
    )
    episode = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="deployed the new build to staging",
            tags=["deploy"],
        ),
    )
    outcome = retrieve(storage, "deploy", node_type=NodeType.EPISODE, limit=5)
    types = {node.type for node, _ in outcome.results}
    assert types <= {NodeType.EPISODE}
    assert episode.id in [node.id for node, _ in outcome.results]


def test_short_and_symbol_tags_trigger_floor(vault, storage):
    """Tags like 'c++' or 'r' must trigger the floor exactly as FTS sees them."""
    cpp_rule = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="always compile with -Wall in this codebase",
            tags=["c++", "compiler"],
        ),
    )
    outcome = retrieve(storage, "how do I build the c++ target", limit=3)
    assert cpp_rule.id in outcome.floor_ids, (
        "single-char token from a symbol tag must still fire the floor"
    )


def test_floor_orders_by_overlap_count(vault, storage):
    """Inside the floor, a rule overlapping 2 query terms beats a 1-term rule."""
    generic = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="generic deploy policy",
            tags=["deploy"],
        ),
    )
    specific = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.CONSTRAINT,
            content="never deploy a release on Fridays",
            tags=["deploy", "release"],
        ),
    )
    outcome = retrieve(storage, "deploy the release", limit=5)
    ids = [node.id for node, _ in outcome.results]
    assert ids.index(specific.id) < ids.index(generic.id), (
        "more overlapping tags = higher floor slot"
    )


def test_mtime_fallback_for_missing_created(vault, storage):
    """A file whose frontmatter lacks `created` must not masquerade as fresh."""
    import os
    import time

    now = datetime.now(UTC)
    fresh = _write(
        vault,
        storage,
        MemoryNode(
            type=NodeType.EPISODE,
            content="weekly report drafted and filed",
            created=now,
            updated=now,
        ),
    )
    # hand-author a node with NO created/updated in frontmatter (supported flow)
    legacy_path = vault / folder_for(NodeType.EPISODE) / "legacy.md"
    legacy_path.write_text(
        "---\nid: legacy-node-0001\ntype: episode\ntags: []\nlinks: []\n---\n"
        "weekly report drafted and filed",
        encoding="utf-8",
    )
    sixty_days_ago = time.time() - 60 * 86400
    os.utime(legacy_path, (sixty_days_ago, sixty_days_ago))
    legacy = MemoryNode.from_file(legacy_path)
    storage.upsert_node(legacy)

    outcome = retrieve(storage, "weekly report drafted", limit=5)
    ids = [node.id for node, _ in outcome.results]
    assert ids.index(fresh.id) < ids.index("legacy-node-0001"), (
        "missing `created` must fall back to file mtime, not parse-time now"
    )
