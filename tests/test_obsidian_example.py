"""The example Obsidian Base must parse and name only keys the package writes."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import NODE_FOLDERS

BASE = Path(__file__).resolve().parents[1] / "examples" / "obsidian" / "memory.base"


def _written_keys() -> set[str]:
    node = MemoryNode(
        type=NodeType.CONCEPT, content="x", source="s", source_hash="h"
    )
    return set(node.to_frontmatter())


def _note_props(names: list[str]) -> set[str]:
    return {
        n.removeprefix("note.")
        for n in names
        if not n.startswith(("file.", "formula."))
    }


def test_memory_base_parses_and_uses_real_keys():
    doc = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert doc["views"], "a Base needs at least one view"

    written = _written_keys()
    formulas = set(doc.get("formulas", {}))
    used: list[str] = list(doc.get("properties", {}))
    for view in doc["views"]:
        assert view["type"] in {"table", "cards", "list"}
        order = view.get("order", [])
        used += order
        for s in view.get("sort", []):
            assert s["property"] in order, "Obsidian only sorts by shown columns"
            used.append(s["property"])
        if "groupBy" in view:
            used.append(view["groupBy"]["property"])

    unknown = _note_props(used) - written
    assert not unknown, f"keys the package never writes: {sorted(unknown)}"
    for name in used:
        if name.startswith("formula."):
            assert name.removeprefix("formula.") in formulas


def test_memory_base_filters_cover_every_node_folder():
    text = BASE.read_text(encoding="utf-8")
    folders = set(re.findall(r'file\.inFolder\("([^"]+)"\)', text))
    assert folders == set(NODE_FOLDERS)
    for value in re.findall(r'type == "([^"]+)"', text):
        assert value in {t.value for t in NodeType}
