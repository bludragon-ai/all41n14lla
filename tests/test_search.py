"""Tests for FTS5 query sanitization and multi-word search semantics.

Regression suite for two successive recall-killers:
1. ``_sanitize`` once wrapped the WHOLE query in one pair of quotes, forcing a
   phrase match that required the terms to be ADJACENT.
2. It then joined terms with FTS5's implicit AND (every term required in one
   note) — which silently returned ``[]`` for natural recall queries whose
   words are spread across different notes (e.g. "Jordan career professional").

The contract now: each term is quoted individually (operators stay
neutralized) and joined with ``OR`` — a note matching ANY term is a candidate,
and BM25 ranks notes matching more (and rarer) terms higher. Single-term
queries are unaffected.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.search import _sanitize, search
from all41n14lla.engine.storage import Storage, default_db_path, folder_for

README_EXAMPLE = "sqlite fts5 uses the porter tokenizer by default"


@pytest.fixture()
def storage(tmp_path: Path):
    for nt in NodeType:
        (tmp_path / folder_for(nt)).mkdir(parents=True, exist_ok=True)
    with Storage(default_db_path(tmp_path)) as s:
        node = MemoryNode(type=NodeType.CONCEPT, content=README_EXAMPLE)
        node.write(tmp_path / folder_for(NodeType.CONCEPT) / f"{node.id}.md")
        s.upsert_node(node)
        yield s


# ── _sanitize unit behavior ──────────────────────────────────────────────────

def test_sanitize_quotes_each_term_individually():
    assert _sanitize("sqlite tokenizer") == '"sqlite" OR "tokenizer"'


def test_sanitize_single_word_unchanged_semantics():
    assert _sanitize("sqlite") == '"sqlite"'


def test_sanitize_strips_embedded_quotes():
    assert _sanitize('sql"ite token"izer') == '"sqlite" OR "tokenizer"'


def test_sanitize_drops_pure_punctuation_terms():
    # an empty FTS5 phrase is a syntax error — terms with no alphanumerics go
    assert _sanitize("sqlite --- !!!") == '"sqlite"'
    assert _sanitize("!!! ???") == ""


def test_sanitize_empty_query():
    assert _sanitize("") == ""
    assert _sanitize("   ") == ""


# ── end-to-end search semantics ──────────────────────────────────────────────

def test_multiword_nonadjacent_terms_match(storage):
    """THE regression: the README quickstart example must return its note."""
    hits = search(storage, "sqlite tokenizer")
    assert hits, "non-adjacent multi-word query must match (AND, not phrase)"
    assert hits[0][0].content == README_EXAMPLE


def test_single_word_still_matches(storage):
    assert search(storage, "sqlite")
    assert search(storage, "tokenizer")


def test_or_semantics_partial_match_does_not_veto(storage):
    """A present term matches even when another query term is absent (OR, not AND)."""
    hits = search(storage, "sqlite kubernetes")  # "kubernetes" absent, "sqlite" present
    assert hits, "a present term must surface the note even if another term is absent"
    assert hits[0][0].content == README_EXAMPLE


def test_more_term_matches_rank_higher(storage):
    """BM25 over OR: the note matching more query terms sorts above one matching fewer."""
    other = MemoryNode(type=NodeType.CONCEPT, content="sqlite is a database")
    other.write(Path(storage.db_path).parent.parent / folder_for(NodeType.CONCEPT) / f"{other.id}.md")
    storage.upsert_node(other)
    hits = search(storage, "sqlite porter tokenizer")  # README note has all 3; "other" has only sqlite
    assert len(hits) == 2
    assert hits[0][0].content == README_EXAMPLE  # 3 matched terms outranks 1


def test_fts_operators_are_neutralized(storage):
    """Operator-looking input is treated as literal terms, never as syntax."""
    # "AND" is quoted to a literal term (absent from the doc); the real words
    # sqlite/tokenizer still match via OR — proving AND wasn't parsed as syntax.
    hits = search(storage, "sqlite AND tokenizer")
    assert hits and hits[0][0].content == README_EXAMPLE
    # ":" neutralized — "content:sqlite" becomes a quoted phrase, absent from the doc.
    assert search(storage, "content:sqlite") == []
    hits = search(storage, "sqlite -porter")  # "-" neutralized, both terms match
    assert hits and hits[0][0].content == README_EXAMPLE


def test_punctuation_only_query_returns_empty_not_error(storage):
    assert search(storage, "!!!") == []
    assert search(storage, "") == []


def test_word_order_does_not_matter(storage):
    assert search(storage, "tokenizer sqlite")
