"""The four node types and the MemoryNode dataclass.

Each node lives as a markdown file with YAML frontmatter::

    ---
    id: <uuid>
    type: concept|pattern|episode|constraint
    tags: [...]
    links: [...]
    created: <iso8601>
    updated: <iso8601>
    stale: false
    decay: 0.0
    ---
    <content body>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import frontmatter


class NodeType(str, Enum):
    CONCEPT = "concept"
    PATTERN = "pattern"
    EPISODE = "episode"
    CONSTRAINT = "constraint"


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return _now()


def _as_list(value: Any) -> list[str]:
    """Coerce a frontmatter list field to ``list[str]``, tolerant like _parse_dt."""
    return [str(item) for item in value] if isinstance(value, (list, tuple)) else []


def _as_float(value: Any) -> float:
    """Coerce a frontmatter float field to ``float``, tolerant like _parse_dt."""
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


@dataclass
class MemoryNode:
    type: NodeType
    content: str
    id: str = field(default_factory=lambda: str(uuid4()))
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    created: datetime = field(default_factory=_now)
    updated: datetime = field(default_factory=_now)
    stale: bool = False
    decay: float = 0.0
    path: Path | None = None

    def to_frontmatter(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "tags": list(self.tags),
            "links": list(self.links),
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "stale": self.stale,
            "decay": self.decay,
        }

    def to_markdown(self) -> str:
        post = frontmatter.Post(self.content, **self.to_frontmatter())
        return frontmatter.dumps(post)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        self.path = path
        return path

    @classmethod
    def from_file(cls, path: Path) -> MemoryNode:
        post = frontmatter.load(str(path))
        meta = post.metadata
        return cls(
            id=str(meta["id"]),
            type=NodeType(meta["type"]),
            tags=_as_list(meta.get("tags")),
            links=_as_list(meta.get("links")),
            created=_parse_dt(meta.get("created")),
            updated=_parse_dt(meta.get("updated")),
            stale=bool(meta.get("stale", False)),
            decay=_as_float(meta.get("decay", 0.0)),
            content=post.content,
            path=path,
        )
