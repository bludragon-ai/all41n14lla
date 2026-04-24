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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import frontmatter


class NodeType(str, Enum):
    CONCEPT = "concept"
    PATTERN = "pattern"
    EPISODE = "episode"
    CONSTRAINT = "constraint"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return _now()


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
    path: Optional[Path] = None

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
    def from_file(cls, path: Path) -> "MemoryNode":
        post = frontmatter.load(str(path))
        meta = post.metadata
        return cls(
            id=str(meta["id"]),
            type=NodeType(meta["type"]),
            tags=list(meta.get("tags") or []),
            links=list(meta.get("links") or []),
            created=_parse_dt(meta.get("created")),
            updated=_parse_dt(meta.get("updated")),
            stale=bool(meta.get("stale", False)),
            decay=float(meta.get("decay", 0.0)),
            content=post.content,
            path=path,
        )
