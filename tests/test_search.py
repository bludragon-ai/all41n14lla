"""Tests for FTS5 query sanitization and multi-word search semantics.

Regression suite for the quickstart-killer: ``_sanitize`` used to wrap the
WHOLE query in one pair of quotes, turning every multi-word query into an
FTS5 phrase match that required the terms to be ADJACENT. The README's own
example — remember "sqlite fts5 uses the porter tokenizer by default", then
``recall "sqlite tokenizer"`` — returned zero matches.

The contract now: each term is quoted individually (operators stay
neutralized) and joined with FTS5's implicit AND (every term must appear,
any position).
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
    assert _sanitize("sqlite tokenizer") == '"sqlite" "tokenizer"'


def test_sanitize_single_word_unchanged_semantics():
    assert _sanitize("sqlite") == '"sqlite"'


def test_sanitize_strips_embedded_quotes():
    assert _sanitize('sql"ite token"izer') == '"sqlite" "tokenizer"'


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


def test_and_semantics_requires_all_terms(storage):
    """A term absent from the document must veto the match (AND, not OR)."""
    assert search(storage, "sqlite kubernetes") == []


def test_fts_operators_are_neutralized(storage):
    """Operator-looking input is treated as literal terms, never as syntax."""
    # would be FTS5 syntax errors / column filters / exclusions if unquoted
    assert search(storage, "sqlite AND tokenizer") == []  # literal "and" not in doc
    assert search(storage, "content:sqlite") == []  # ":" neutralized, term "content:sqlite" absent
    hits = search(storage, "sqlite -porter")  # "-" neutralized, term matches "porter"
    assert hits and hits[0][0].content == README_EXAMPLE


def test_punctuation_only_query_returns_empty_not_error(storage):
    assert search(storage, "!!!") == []
    assert search(storage, "") == []


def test_word_order_does_not_matter(storage):
    assert search(storage, "tokenizer sqlite")
