"""Verifiable erasure — forget by source, and get a receipt.

The fourth governance question (`all41n14lla-v2/SPEC.md`): *can you prove you deleted it?*
Right-to-erasure is a request someone has to ANSWER, not just perform. So every forget — by id
or by source — removes the file and the index rows, then writes a receipt into
`<vault>/.all41n14lla/erasures/`: what was deleted (ids + a hash of each content, so the receipt
can vouch for what went without keeping it), how many, when, and a re-scan of the vault proving
zero remain for that source. The receipt is plain JSON on your disk, like everything else.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode
from all41n14lla.engine.storage import Storage, default_db_path

logger = logging.getLogger(__name__)


@dataclass
class Receipt:
    when: str
    vault: str
    source: str | None            # the source pattern erased, or None for an id-based forget
    deleted: list[dict] = field(default_factory=list)   # {id, type, source, content_sha256}
    count: int = 0
    remaining_after_rescan: int = 0
    path: str = ""                # where this receipt was written


def _content_sha(node: MemoryNode) -> str:
    return hashlib.sha256(node.content.encode("utf-8")).hexdigest()


def _matches(node_source: str | None, pattern: str) -> bool:
    if not node_source:
        return False
    p = pattern.strip().rstrip("/")
    return node_source == p or node_source.startswith(p + "/") or fnmatch.fnmatch(node_source, p)


def iter_nodes(vault: Path):
    for p in sorted(vault.rglob("*.md")):
        if p.parent == vault or p.name in {"README.md", "PERSONA.md"}:
            continue
        try:
            yield MemoryNode.from_file(p)
        except Exception as exc:  # noqa: BLE001 — a stray markdown file is not a node; never crash an erasure
            logger.debug("skipping %s: not a memory node (%s)", p, exc)
            continue


def find_by_source(vault: Path, pattern: str) -> list[MemoryNode]:
    return [n for n in iter_nodes(vault) if _matches(n.source, pattern)]


def rescan(vault: Path, pattern: str) -> int:
    return len(find_by_source(vault, pattern))


def erase(vault: Path, nodes: list[MemoryNode], source: str | None = None) -> Receipt:
    """Delete *nodes* (file + index) and write a receipt. Re-scans for *source* afterwards."""
    vault = vault.expanduser().resolve()
    receipt = Receipt(when=datetime.now(UTC).isoformat(timespec="seconds"), vault=str(vault), source=source)
    with Storage(default_db_path(vault)) as storage:
        for n in nodes:
            receipt.deleted.append({"id": n.id, "type": n.type.value, "source": n.source, "content_sha256": _content_sha(n)})
            storage.delete_node(n.id)
            if n.path and n.path.exists():
                n.path.unlink()
    receipt.count = len(receipt.deleted)
    receipt.remaining_after_rescan = rescan(vault, source) if source else sum(
        1 for m in iter_nodes(vault) if m.id in {d["id"] for d in receipt.deleted}
    )
    out = vault / ".all41n14lla" / "erasures"
    out.mkdir(parents=True, exist_ok=True)
    stamp = receipt.when.replace(":", "").replace("+00:00", "Z")
    path = out / f"{stamp}-{(source or 'id').replace('/', '_').replace('*', 'x')[:40]}.json"
    receipt.path = str(path)
    path.write_text(json.dumps(asdict(receipt), indent=2), encoding="utf-8")
    return receipt
