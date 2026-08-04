"""Tests for the ``consolidate`` engine (pathways v0.2).

Covers tag co-occurrence rebuild, threshold promotion, decay, orphan pruning,
idempotency, dry-run, and the no-mutation guarantee on existing nodes.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.pathways import (
    AUTO_TAGS,
    consolidate,
    decay_multiplier,
    tag_cooccurrence,
)
from all41n14lla.engine.storage import (
    NODE_FOLDERS,
    Storage,
    default_db_path,
    folder_for,
)

T0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _make_vault(root: Path) -> Path:
    for folder in NODE_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    return root


def _node(
    vault: Path,
    storage: Storage,
    node_type: NodeType,
    text: str,
    tags: list[str],
    *,
    created: datetime = T0,
) -> str:
    node = MemoryNode(
        type=node_type, content=text, tags=tags, created=created, updated=created
    )
    node.write(vault / folder_for(node_type) / f"{node.id}.md")
    storage.upsert_node(node)
    return node.id


def _concept(vault, storage, text, tags, **kw) -> str:
    return _node(vault, storage, NodeType.CONCEPT, text, tags, **kw)


def _neighbors(storage: Storage, node_id: str) -> dict[str, float]:
    """Mirror inspect's neighbor query: top weighted edges, both directions."""
    rows = storage.conn.execute(
        """
        SELECT dst_id AS nid, weight FROM edges WHERE src_id = ?
        UNION
        SELECT src_id AS nid, weight FROM edges WHERE dst_id = ?
        """,
        (node_id, node_id),
    ).fetchall()
    return {r["nid"]: float(r["weight"]) for r in rows}


def _pattern_files(vault: Path) -> list[Path]:
    return sorted((vault / "patterns").glob("*.md"))


# ── pure functions ────────────────────────────────────────────────────────────


def test_decay_multiplier_math():
    assert decay_multiplier(0) == 1.0
    assert decay_multiplier(-5) == 1.0  # never amplifies
    assert decay_multiplier(30) == pytest.approx(0.9)
    assert decay_multiplier(60) == pytest.approx(0.81)
    assert decay_multiplier(15) == pytest.approx(0.9 ** 0.5)


def test_tag_cooccurrence_counts_shared_tags():
    a = MemoryNode(type=NodeType.CONCEPT, content="A", tags=["x", "y", "z"], id="a")
    b = MemoryNode(type=NodeType.CONCEPT, content="B", tags=["x", "y"], id="b")
    c = MemoryNode(type=NodeType.CONCEPT, content="C", tags=["z"], id="c")
    weights, shared = tag_cooccurrence({"a": a, "b": b, "c": c})
    assert weights[("a", "b")] == 2.0          # share x, y
    assert weights[("a", "c")] == 1.0          # share z
    assert ("b", "c") not in weights           # share nothing
    assert shared[("a", "b")] == {"x", "y"}


def test_tag_cooccurrence_ignores_provenance_tags():
    # AUTO_TAGS must not create edges between auto-generated patterns.
    p1 = MemoryNode(type=NodeType.PATTERN, content="p1", tags=list(AUTO_TAGS), id="p1")
    p2 = MemoryNode(type=NodeType.PATTERN, content="p2", tags=list(AUTO_TAGS), id="p2")
    weights, _ = tag_cooccurrence({"p1": p1, "p2": p2})
    assert weights == {}


def test_tag_cooccurrence_is_case_insensitive():
    a = MemoryNode(type=NodeType.CONCEPT, content="A", tags=["Career"], id="a")
    b = MemoryNode(type=NodeType.CONCEPT, content="B", tags=["career"], id="b")
    weights, _ = tag_cooccurrence({"a": a, "b": b})
    assert weights[("a", "b")] == 1.0


# ── edge rebuild ──────────────────────────────────────────────────────────────


def test_consolidate_builds_edges_inspect_sees_them(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "Concept A", ["career", "identity", "founder"])
        b = _concept(vault, s, "Concept B", ["career", "identity", "founder"])
        c = _concept(vault, s, "Concept C", ["career"])

        assert _neighbors(s, a) == {}  # empty before consolidate

        summary = consolidate(s, vault, now=T0)

        assert summary["nodes_scanned"] == 3
        assert summary["by_type"]["concept"] == 3
        # pairs: (a,b)=3 shared, (a,c)=1, (b,c)=1  -> 3 edges
        assert summary["edges_written"] == 3
        assert _neighbors(s, a)[b] == 3.0
        assert _neighbors(s, a)[c] == 1.0
        assert _neighbors(s, b)[c] == 1.0


def test_consolidate_survives_missing_node_folder(tmp_path: Path):
    """Regression: the disk_ids scan must not crash when a node folder is absent.

    On Python 3.11, ``Path.glob()`` on a missing directory raises
    ``FileNotFoundError`` — a vault whose subfolder was deleted after init (or
    never created) must still consolidate.
    """
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "Concept A", ["career", "identity"])
        b = _concept(vault, s, "Concept B", ["career", "identity"])

        # Remove an unrelated (empty) node folder to simulate a partial vault.
        removed = next(f for f in NODE_FOLDERS if f != folder_for(NodeType.CONCEPT))
        (vault / removed).rmdir()

        summary = consolidate(s, vault, now=T0)

        assert summary["nodes_scanned"] == 2
        assert _neighbors(s, a)[b] == 2.0


# ── promotion ─────────────────────────────────────────────────────────────────


def test_promotion_fires_at_threshold(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "Concept A body", ["career", "identity", "founder"])
        b = _concept(vault, s, "Concept B body", ["career", "identity", "founder"])
        _concept(vault, s, "Concept C body", ["career"])

        summary = consolidate(s, vault, threshold=3.0, now=T0)

        assert len(summary["promotions"]) == 1
        promo = summary["promotions"][0]
        assert sorted(promo["source_nodes"]) == sorted([a, b])
        assert promo["weight"] == 3.0
        assert promo["shared_tags"] == ["career", "founder", "identity"]

        files = _pattern_files(vault)
        assert len(files) == 1
        minted = MemoryNode.from_file(files[0])
        assert minted.type is NodeType.PATTERN
        assert set(AUTO_TAGS).issubset(set(minted.tags))
        assert "unreviewed" in minted.tags          # the reviewed:false flag
        assert sorted(minted.links) == sorted([a, b])  # source_nodes
        for tag in ("career", "identity", "founder"):
            assert tag in minted.tags


def test_no_promotion_below_threshold(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["career", "identity", "founder"])
        _concept(vault, s, "B", ["career", "identity", "founder"])

        summary = consolidate(s, vault, threshold=4.0, now=T0)

        assert summary["promotions"] == []
        assert summary["edges_written"] == 1  # edge still built
        assert _pattern_files(vault) == []


def test_promote_false_skips_patterns_but_builds_edges(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])

        summary = consolidate(s, vault, threshold=3.0, promote=False, now=T0)

        assert summary["promotions"] == []
        assert summary["candidates"] == []
        assert summary["edges_written"] == 1
        assert _pattern_files(vault) == []


def test_promotion_concepts_only(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        # Episodes and constraints share 3 tags but must NOT promote.
        _node(vault, s, NodeType.EPISODE, "E1", ["a", "b", "c"])
        _node(vault, s, NodeType.EPISODE, "E2", ["a", "b", "c"])
        _node(vault, s, NodeType.CONSTRAINT, "K1", ["a", "b", "c"])

        summary = consolidate(s, vault, threshold=3.0, now=T0)

        assert summary["promotions"] == []
        assert _pattern_files(vault) == []
        # but the edges between them still exist
        assert summary["edges_written"] >= 3


def test_existing_pattern_blocks_duplicate_promotion(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x", "y", "z"])
        b = _concept(vault, s, "B", ["x", "y", "z"])
        # A human pattern already links A & B.
        human = MemoryNode(
            type=NodeType.PATTERN, content="human", tags=["mine"], links=[a, b]
        )
        human.write(vault / folder_for(NodeType.PATTERN) / f"{human.id}.md")
        s.upsert_node(human)

        summary = consolidate(s, vault, threshold=3.0, now=T0)

        assert summary["promotions"] == []
        assert len(summary["candidates"]) == 1
        assert summary["candidates"][0]["already_promoted"] is True
        assert len(_pattern_files(vault)) == 1  # only the human one


# ── idempotency ───────────────────────────────────────────────────────────────


def test_consolidate_is_idempotent(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])

        first = consolidate(s, vault, threshold=3.0, now=T0)
        # Re-run back-to-back: weights must NOT double, no second pattern.
        second = consolidate(s, vault, threshold=3.0, now=T0)

        weight = s.conn.execute("SELECT weight FROM edges").fetchall()
        assert len(weight) == 1
        assert weight[0]["weight"] == 3.0       # SET, not incremented
        assert len(first["promotions"]) == 1
        assert second["promotions"] == []       # already covered
        assert len(_pattern_files(vault)) == 1  # exactly one


# ── decay + prune ─────────────────────────────────────────────────────────────


def test_stale_edge_decays_when_cooccurrence_drops(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x", "y"])
        b_id = _concept(vault, s, "B", ["x", "y"])

        consolidate(s, vault, threshold=99, now=T0)  # edge a-b weight 2, no promo
        assert _neighbors(s, a)[b_id] == 2.0

        # Re-tag A so it no longer shares any tag with B.
        a_node = MemoryNode.from_file(vault / "concepts" / f"{a}.md")
        a_node.tags = ["q"]
        a_node.write(a_node.path)

        later = T0 + timedelta(days=30)
        summary = consolidate(s, vault, threshold=99, now=later)

        assert summary["edges_decayed"] == 1
        assert _neighbors(s, a).get(b_id) == pytest.approx(2.0 * 0.9)  # one period


def test_orphan_edges_are_pruned(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x"])
        # Inject an edge to a node that does not exist.
        s.conn.execute(
            "INSERT INTO edges (src_id, dst_id, weight, updated) VALUES (?, ?, ?, ?)",
            (min(a, "ghost"), max(a, "ghost"), 5.0, T0.isoformat()),
        )
        s.conn.commit()

        summary = consolidate(s, vault, now=T0)

        assert summary["edges_pruned"] == 1
        remaining = s.conn.execute("SELECT * FROM edges").fetchall()
        assert all("ghost" not in (r["src_id"], r["dst_id"]) for r in remaining)


# ── safety: no mutation, dry-run ──────────────────────────────────────────────


def test_consolidate_never_mutates_existing_nodes(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])

        before = {
            p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (vault / "concepts").glob("*.md")
        }

        consolidate(s, vault, threshold=3.0, now=T0)

        after = {
            p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (vault / "concepts").glob("*.md")
        }
        assert before == after  # source concepts untouched


def test_dry_run_writes_nothing(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])

        summary = consolidate(s, vault, threshold=3.0, dry_run=True, now=T0)

        assert summary["dry_run"] is True
        assert summary["edges_written"] == 1            # reports what WOULD happen
        assert len(summary["candidates"]) == 1
        assert summary["candidates"][0]["already_promoted"] is False
        # ...but nothing was persisted.
        assert s.conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"] == 0
        assert _pattern_files(vault) == []


def test_dry_run_skips_reconcile(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y"])
        b = _concept(vault, s, "B", ["x", "y"])
        (vault / "concepts" / f"{b}.md").unlink()  # file gone, index row stays

        summary = consolidate(s, vault, dry_run=True, now=T0)

        assert summary["indexed"] == 0  # reconcile not run in dry-run
        # B's stale index row is left untouched (no reconcile).
        assert s.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (b,)).fetchone() is not None


# ── durability (the gap that matters most for a vault writer) ──────────────────


def test_edges_and_patterns_persist_after_reopen(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    db = default_db_path(vault)
    with Storage(db) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])
        summary = consolidate(s, vault, threshold=3.0, now=T0)
        pid = summary["promotions"][0]["id"]

    # Fresh connection on the same DB file — proves the commit actually landed.
    with Storage(db) as s2:
        weights = [r["weight"] for r in s2.conn.execute("SELECT weight FROM edges").fetchall()]
        assert 3.0 in weights
        assert s2.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (pid,)).fetchone() is not None


# ── tag normalization + cliques ───────────────────────────────────────────────


def test_tag_normalization_dedupes_whitespace_and_case(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["career", " career ", "CAREER"])
        b = _concept(vault, s, "B", ["career"])
        consolidate(s, vault, threshold=99, now=T0)
        # Three spellings of one tag on A must collapse -> weight 1, not 3.
        assert _neighbors(s, a).get(b) == 1.0


def test_clique_three_nodes_sharing_a_tag(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["t"])
        b = _concept(vault, s, "B", ["t"])
        c = _concept(vault, s, "C", ["t"])
        summary = consolidate(s, vault, threshold=99, now=T0)
        assert summary["edges_written"] == 3  # C(3,2)
        assert _neighbors(s, a) == {b: 1.0, c: 1.0}
        assert _neighbors(s, b) == {a: 1.0, c: 1.0}


# ── promotion edge cases ──────────────────────────────────────────────────────


def test_cross_type_pair_builds_edge_but_no_promotion(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        c = _concept(vault, s, "C", ["a", "b", "c"])
        e = _node(vault, s, NodeType.EPISODE, "E", ["a", "b", "c"])
        summary = consolidate(s, vault, threshold=3.0, now=T0)
        assert _neighbors(s, c).get(e) == 3.0   # edge exists
        assert summary["promotions"] == []      # mixed pair never promotes
        assert _pattern_files(vault) == []


def test_multiple_promotions_in_one_run(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["p", "q", "r"])
        _concept(vault, s, "B", ["p", "q", "r"])
        _concept(vault, s, "C", ["s", "t", "u", "v"])
        _concept(vault, s, "D", ["s", "t", "u", "v"])
        summary = consolidate(s, vault, threshold=3.0, now=T0)
        assert len(summary["promotions"]) == 2
        assert len(_pattern_files(vault)) == 2
        ws = [c["weight"] for c in summary["candidates"]]
        assert ws == sorted(ws, reverse=True)  # highest weight first


# ── decay round-trip + auto-pattern isolation ─────────────────────────────────


def test_decayed_edge_resets_when_cooccurrence_returns(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x", "y"])
        b = _concept(vault, s, "B", ["x", "y"])
        consolidate(s, vault, threshold=99, now=T0)               # weight 2

        node = MemoryNode.from_file(vault / "concepts" / f"{a}.md")
        node.tags = ["q"]
        node.write(node.path)
        consolidate(s, vault, threshold=99, now=T0 + timedelta(days=30))  # decays to 1.8
        assert _neighbors(s, a).get(b) == pytest.approx(2.0 * 0.9)

        node2 = MemoryNode.from_file(vault / "concepts" / f"{a}.md")
        node2.tags = ["x", "y"]
        node2.write(node2.path)
        consolidate(s, vault, threshold=99, now=T0 + timedelta(days=60))  # SET fresh
        assert _neighbors(s, a).get(b) == pytest.approx(2.0)  # reset, not 1.8 or 3.8


def test_double_decay_same_timestamp_is_noop(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x", "y"])
        b = _concept(vault, s, "B", ["x", "y"])
        consolidate(s, vault, threshold=99, now=T0)

        node = MemoryNode.from_file(vault / "concepts" / f"{a}.md")
        node.tags = ["q"]
        node.write(node.path)
        later = T0 + timedelta(days=30)
        consolidate(s, vault, threshold=99, now=later)          # decays once -> 1.8
        again = consolidate(s, vault, threshold=99, now=later)  # same clock -> no further decay
        assert again["edges_decayed"] == 0
        assert _neighbors(s, a).get(b) == pytest.approx(1.8)


def test_auto_pattern_not_reedged_on_second_run(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y", "z"])
        _concept(vault, s, "B", ["x", "y", "z"])
        first = consolidate(s, vault, threshold=3.0, now=T0)
        pid = first["promotions"][0]["id"]
        consolidate(s, vault, threshold=3.0, now=T0)  # 2nd run scans the new pattern
        # The auto-pattern carries x/y/z but must NOT bind to its source concepts.
        assert _neighbors(s, pid) == {}


# ── reconcile + orphan hardening + degenerate input ───────────────────────────


def test_reconcile_drops_deleted_node_and_indexed_count(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y"])
        b = _concept(vault, s, "B", ["x", "y"])
        (vault / "concepts" / f"{b}.md").unlink()  # delete on disk

        summary = consolidate(s, vault, now=T0)

        assert summary["indexed"] == 1        # only A remains on disk
        assert summary["nodes_scanned"] == 1
        assert s.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (b,)).fetchone() is None
        assert s.conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"] == 0


def test_unparseable_file_does_not_prune_its_edges(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", ["x", "y"])
        _concept(vault, s, "B", ["x", "y"])
        consolidate(s, vault, threshold=99, now=T0)  # edge a-b weight 2
        assert s.conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"] == 1

        # Corrupt A's frontmatter but leave the file ON DISK.
        (vault / "concepts" / f"{a}.md").write_text("garbage, no frontmatter", encoding="utf-8")
        summary = consolidate(s, vault, threshold=99, now=T0 + timedelta(days=1))

        # A is still on disk -> its edge is decayed, NOT pruned as an orphan.
        assert summary["edges_pruned"] == 0
        assert s.conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"] == 1


def test_empty_and_none_tags_produce_no_edges(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        a = _concept(vault, s, "A", [])
        b = _concept(vault, s, "B", ["", "  "])  # blank entries skipped
        c = _concept(vault, s, "C", ["real"])
        summary = consolidate(s, vault, now=T0)
        assert summary["edges_written"] == 0
        assert _neighbors(s, a) == {}
        assert _neighbors(s, b) == {}
        assert _neighbors(s, c) == {}


def test_default_clock_runs_and_stamps_recent(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "A", ["x", "y"])
        _concept(vault, s, "B", ["x", "y"])
        summary = consolidate(s, vault)  # now=None -> real UTC clock
        assert summary["edges_written"] == 1
        ts = s.conn.execute("SELECT updated FROM edges").fetchone()["updated"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None  # tz-aware UTC stamp


def test_by_type_counts_all_node_types(tmp_path: Path):
    vault = _make_vault(tmp_path / "vault")
    with Storage(default_db_path(vault)) as s:
        _concept(vault, s, "C1", ["x"])
        _concept(vault, s, "C2", ["x"])
        _node(vault, s, NodeType.EPISODE, "E1", ["x"])
        _node(vault, s, NodeType.CONSTRAINT, "K1", ["x"])
        summary = consolidate(s, vault, now=T0)
        assert summary["by_type"] == {
            "concept": 2,
            "pattern": 0,
            "episode": 1,
            "constraint": 1,
        }
