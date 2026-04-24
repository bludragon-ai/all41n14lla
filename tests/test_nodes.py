"""Round-trip tests for MemoryNode frontmatter."""
from __future__ import annotations

from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType


def test_create_and_serialize():
    node = MemoryNode(type=NodeType.CONCEPT, content="A concept.", tags=["test"])
    md = node.to_markdown()
    assert "type: concept" in md
    assert "A concept." in md


def test_roundtrip(tmp_path: Path):
    original = MemoryNode(
        type=NodeType.EPISODE,
        content="A thing happened.",
        tags=["event"],
        links=["abc-123"],
    )
    path = tmp_path / "episodes" / f"{original.id}.md"
    original.write(path)

    loaded = MemoryNode.from_file(path)

    assert loaded.id == original.id
    assert loaded.type is NodeType.EPISODE
    assert loaded.content.strip() == "A thing happened."
    assert loaded.tags == ["event"]
    assert loaded.links == ["abc-123"]
    assert loaded.stale is False
    assert loaded.decay == 0.0
