"""Predator — devour a path to gain what it knows. Consent-scoped, by construction.

In the episode, Predator eats only what the protagonist chooses to eat, and each meal is
confirmed as an ability gained. Here: point it at ONE path, it analyzes and PROPOSES; nothing is
written until you accept. That is not a safety feature bolted on — it is the product
(`all41n14lla-v2/SPEC.md`: install → auto-ingest-everything is the anti-pattern this exists to
prevent).

v1 is deterministic and explainable — no model in the loop, so the proposal is reproducible and
the tests can pin it:
- markdown: the title + first paragraph becomes a concept candidate; every line that starts
  with never / always / must not / do not becomes a constraint candidate.
- code: the module docstring or leading comment block becomes a concept candidate.
- everything else (binaries, data, generated dirs) is skipped and counted, not read.
Every written node carries `source` (relative path) and `source_hash` (sha256 of the file), so
"where did this come from?" is answered by the file itself. A file already devoured, unchanged,
is not proposed again.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import Storage, default_db_path, folder_for
from all41n14lla.reincarnate import act_tags

TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".sh", ".rb"}
CODE_EXT = TEXT_EXT - {".md", ".markdown", ".txt", ".rst"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".next",
             ".expo", "target", ".cache", ".idea", ".vscode", "coverage", ".tox", ".mypy_cache", ".ruff_cache"}
MAX_FILES = 200
MAX_BYTES = 200_000
CONCEPT_CAP = 600
RULE_CAP = 300
_RULE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*)?(never|always|must not|must never|do not|don't|do NOT)\b", re.IGNORECASE)
_HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Candidate:
    kind: NodeType
    content: str
    tags: tuple[str, ...]
    source: str       # path relative to the devoured root (or the file name for a single file)
    source_hash: str  # sha256 of the whole source file
    where: str        # human locator, e.g. "README.md:12"

    @property
    def skill(self) -> str:
        return self.tags[-1]


@dataclass
class Analysis:
    root: Path
    candidates: list[Candidate] = field(default_factory=list)
    files_read: int = 0
    files_skipped: int = 0
    already_devoured: int = 0
    truncated: bool = False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS or part.startswith(".") and part not in {".", ".."} for part in p.relative_to(root).parts[:-1]):
            continue
        if p.name.startswith(".") and p.is_file():
            continue
        if p.is_file():
            yield p


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            return m.group(1).strip()
    return fallback


def _first_paragraph(text: str) -> str:
    body: list[str] = []
    started = False
    for line in text.splitlines():
        s = line.strip()
        if not started:
            if not s or s.startswith(("#", "---", "[!", "<", "![")):
                continue
            started = True
        if started:
            if not s:
                break
            if s.startswith("#"):
                break
            body.append(s)
    return " ".join(body)


def _docstring(text: str, ext: str) -> str:
    if ext == ".py":
        m = re.match(r'\s*(?:#[^\n]*\n|\s)*?[rub]*("""|\'\'\')(.*?)\1', text, re.DOTALL)
        if m:
            return " ".join(m.group(2).split())
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("#!", "# -*-")):
            continue
        if s.startswith(("#", "//", "/*", "*", "--")):
            lines.append(s.lstrip("#/* -").strip())
        elif lines or s:
            break
    return " ".join(x for x in lines if x)


def _relative(root: Path, p: Path) -> str:
    return p.name if root.is_file() else str(p.relative_to(root))


def analyze(root: Path, existing_hashes: set[str] | None = None, max_files: int = MAX_FILES) -> Analysis:
    """Read one path and propose memories. Reads text only; writes nothing."""
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    existing_hashes = existing_hashes or set()
    a = Analysis(root=root)
    for p in _iter_files(root):
        if a.files_read >= max_files:
            a.truncated = True
            break
        ext = p.suffix.lower()
        if ext not in TEXT_EXT or p.stat().st_size > MAX_BYTES:
            a.files_skipped += 1
            continue
        raw = p.read_bytes()
        digest = _sha(raw)
        if digest in existing_hashes:
            a.already_devoured += 1
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            a.files_skipped += 1
            continue
        a.files_read += 1
        rel = _relative(root, p)
        if ext in CODE_EXT:
            doc = _docstring(text, ext)
            if doc:
                a.candidates.append(Candidate(NodeType.CONCEPT, f"{rel}: {doc[:CONCEPT_CAP]}",
                                              ("devoured", "code", rel.rsplit("/", 1)[-1]), rel, digest, f"{rel}:1"))
            continue
        title = _title(text, p.stem)
        para = _first_paragraph(text)
        if para:
            a.candidates.append(Candidate(NodeType.CONCEPT, f"{title} — {para[:CONCEPT_CAP]}",
                                          ("devoured", "doc", title[:60]), rel, digest, f"{rel}:1"))
        for i, line in enumerate(text.splitlines(), 1):
            if _RULE.match(line):
                rule = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?", "", line).strip().strip("*")
                if len(rule) < 12:
                    continue
                tags = ("devoured", "rule", *act_tags(rule), f"{title[:40]} · rule")
                a.candidates.append(Candidate(NodeType.CONSTRAINT, rule[:RULE_CAP], tags, rel, digest, f"{rel}:{i}"))
    return a


def existing_source_hashes(vault: Path) -> set[str]:
    out: set[str] = set()
    for p in vault.rglob("*.md"):
        if p.parent == vault:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:1200]
        except OSError:
            continue
        m = re.search(r"^source_hash:\s*['\"]?([0-9a-f]{64})", head, re.MULTILINE)
        if m:
            out.add(m.group(1))
    return out


def consume(vault: Path, analysis: Analysis, accept: list[int] | None, say: Callable[[str], None] = print) -> list[MemoryNode]:
    """Write the accepted candidates (1-based indexes; None = all) with provenance, plus one
    episode that records the meal. Returns the nodes written (episode last)."""
    chosen = analysis.candidates if accept is None else [analysis.candidates[i - 1] for i in accept]
    if not chosen:
        return []
    written: list[MemoryNode] = []
    for c in chosen:
        node = MemoryNode(type=c.kind, content=c.content, tags=list(c.tags), links=[],
                          source=c.source, source_hash=c.source_hash)
        node.write(vault / folder_for(c.kind) / f"{node.id}.md")
        written.append(node)
        say(f"《Confirmed.》 {'Skill' if c.kind is NodeType.CONSTRAINT else 'Knowledge'} [{c.skill}] devoured · {c.where}")
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    episode = MemoryNode(type=NodeType.EPISODE,
                         content=f"Devoured {analysis.root} {when}: {len(written)} memories from {analysis.files_read} files.",
                         tags=["devour", "predator"], links=[n.id for n in written])
    episode.write(vault / folder_for(NodeType.EPISODE) / f"{episode.id}.md")
    with Storage(default_db_path(vault)) as storage:
        for n in [*written, episode]:
            storage.upsert_node(n)
        storage.increment_edges([n.id for n in written])
    return [*written, episode]


def parse_accept(value: str | None, total: int) -> list[int] | None:
    """'all' → None (everything); '1,3,5' → [1,3,5]; validates range."""
    if value is None or value.strip().lower() == "all":
        return None
    picks: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            picks.extend(range(int(lo), int(hi) + 1))
        else:
            picks.append(int(part))
    bad = [i for i in picks if i < 1 or i > total]
    if bad:
        raise ValueError(f"no such candidate(s): {bad} (1–{total})")
    return sorted(set(picks))
