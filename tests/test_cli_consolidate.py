"""CLI rendering tests for ``all41n14lla consolidate`` (the rich-table paths)."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from all41n14lla.cli import app
from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import (
    NODE_FOLDERS,
    Storage,
    default_db_path,
    folder_for,
)

runner = CliRunner()


def _vault_with_two_concepts(tmp_path: Path, tags: list[str]) -> Path:
    vault = tmp_path / "vault"
    for folder in NODE_FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    with Storage(default_db_path(vault)) as s:
        for text in ("Concept A", "Concept B"):
            node = MemoryNode(type=NodeType.CONCEPT, content=text, tags=tags)
            node.write(vault / folder_for(NodeType.CONCEPT) / f"{node.id}.md")
            s.upsert_node(node)
    return vault


def test_cli_consolidate_mints_and_renders(tmp_path: Path):
    vault = _vault_with_two_concepts(tmp_path, ["career", "ai", "founder"])
    result = runner.invoke(app, ["consolidate", "--vault", str(vault), "--threshold", "3"])
    assert result.exit_code == 0, result.output
    assert "Consolidated" in result.output
    assert "Minted" in result.output


def test_cli_consolidate_dry_run_renders(tmp_path: Path):
    vault = _vault_with_two_concepts(tmp_path, ["career", "ai", "founder"])
    result = runner.invoke(
        app, ["consolidate", "--vault", str(vault), "--threshold", "3", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output
    assert "Minted" not in result.output  # dry-run mints nothing


def test_cli_consolidate_empty_state_renders(tmp_path: Path):
    vault = _vault_with_two_concepts(tmp_path, ["solo"])  # share 1 tag, below threshold 3
    result = runner.invoke(app, ["consolidate", "--vault", str(vault), "--threshold", "3"])
    assert result.exit_code == 0, result.output
    assert "nothing to promote" in result.output
