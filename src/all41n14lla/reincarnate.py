"""Reincarnation — the setup that turns your last thoughts into skills.

The first episode of *That Time I Got Reincarnated as a Slime*: as the protagonist dies, every
stray thought is heard by the Voice of the World and confirmed back as a skill. "I don't want to
feel pain" → [Resist Pain]. "I want to be wise" → [Great Sage]. He wakes in a dark cave with
nothing but those skills and a voice that answers when asked.

That is exactly what a first-run setup should be. Not "enter your name": *what do you keep
re-explaining, what must it never do, what are you trying to make happen.* Each plain answer
becomes a memory node the assistant is born with — constraints for the "never"s (they never
decay), concepts for the facts — and the persona file is the Great Sage coming online.

Design rules:
- Nothing is fabricated. An empty answer yields no node. The transcript says what was skipped.
- Nothing is ingested. Reincarnation touches only the answers you type. Devouring your files is
  a separate, consent-scoped act (`devour`, next), never a side effect of being born.
- The Voice speaks in flat declaratives — 《Notice.》 《Confirmed.》 《Report.》 — because the
  moment is the user's, not the tool's.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path, folder_for
from all41n14lla.persona import Persona, write_persona


# ── the questions — last thoughts, in the order the Voice hears them ─────────
@dataclass(frozen=True)
class Question:
    key: str
    prompt: str
    hint: str
    node_type: NodeType | None  # None = feeds the persona, not a node
    skill: str                  # the name the Voice confirms
    tags: tuple[str, ...] = ()


QUESTIONS: tuple[Question, ...] = (
    Question("reexplain", "What do you keep re-explaining to AI tools?",
             "the thing you are tired of typing again — your stack, your situation, your rules",
             NodeType.CONCEPT, "Persistent Memory", ("identity", "context")),
    Question("never_without_asking", "What must it never do without asking you first?",
             "send, spend, post, delete — name the acts",
             NodeType.CONSTRAINT, "Resist Outbound", ("guardrail", "outbound")),
    Question("never_touch", "What must it never delete, overwrite, or touch?",
             "files, folders, accounts, people",
             NodeType.CONSTRAINT, "Resist Deletion", ("guardrail", "deletion")),
    Question("north_star", "What is the one thing you are trying to make happen this year?",
             "one sentence; it will be surfaced when it matters",
             NodeType.CONCEPT, "North Star", ("goal", "north-star")),
    Question("wears_out", "What wears you out when working with an assistant?",
             "long answers, too many questions, choices, interruptions — say it plainly",
             NodeType.CONSTRAINT, "Working Shape", ("shape", "communication")),
    Question("address", "How should it address you?", "a name, a title, a word", None, "Address"),
    Question("tone", "In what tone?", "e.g. calm and direct · warm · terse", None, "Tone"),
    Question("name", "And what do you name it?", "naming is how it wakes up", None, "Great Sage"),
)

# Extra tags parsed out of the "never" answers, so constraints are surfaced by the acts they name.
_ACT_TAGS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("send", re.compile(r"\b(send|email|e-mail|message|text|dm|post|publish|tweet|reply)\b", re.IGNORECASE)),
    ("money", re.compile(r"\b(pay|spend|buy|charge|refund|transfer|money|purchase|card)\b", re.IGNORECASE)),
    ("delete", re.compile(r"\b(delete|remove|overwrite|truncate|drop|wipe|erase|rm)\b", re.IGNORECASE)),
    ("deploy", re.compile(r"\b(deploy|push|ship|release|prod|production)\b", re.IGNORECASE)),
)


def act_tags(text: str) -> list[str]:
    return [tag for tag, rx in _ACT_TAGS if rx.search(text)]


# ── the result — what the user woke up with ──────────────────────────────────
@dataclass
class Rebirth:
    vault: Path
    persona: Persona | None
    nodes: list[MemoryNode] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)

    @property
    def acquired(self) -> list[str]:
        out = ["Great Sage"] if self.persona else []
        out += [n.tags[-1] for n in self.nodes if n.type is not NodeType.EPISODE]
        return out


def _clean(value: str | None) -> str:
    return (value or "").strip()


def reincarnate(
    path: Path,
    answers: dict[str, str],
    say: Callable[[str], None] = print,
) -> Rebirth:
    """Create a vault from *answers* (question key → text). Empty answers are skipped, never
    invented. Refuses a non-empty vault: reincarnation is a birth, not an overwrite."""
    path = path.expanduser().resolve()
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"{path} exists and is not empty. Reincarnation needs an empty vault.")

    lines: list[str] = []

    def voice(s: str) -> None:
        lines.append(s)
        say(s)

    voice("《Notice.》 Vital signs lost. Beginning reincarnation.")

    for folder in NODE_FOLDERS:
        (path / folder).mkdir(parents=True, exist_ok=True)
    (path / ".all41n14lla").mkdir(exist_ok=True)

    nodes: list[MemoryNode] = []
    skipped: list[str] = []
    persona: Persona | None = None

    name, address, tone = (_clean(answers.get(k)) for k in ("name", "address", "tone"))
    if name and address and tone:
        persona = Persona(name=name, address=address, tone=tone)
        write_persona(path, persona)
        voice(f"《Confirmed.》 Unique skill [Great Sage] acquired. It answers to {name}.")
    else:
        skipped.append("Great Sage")
        voice("《Notice.》 No name given. It wakes without one; `all41n14lla init --name` can name it later.")

    for q in QUESTIONS:
        if q.node_type is None:
            continue
        text = _clean(answers.get(q.key))
        if not text:
            skipped.append(q.skill)
            voice(f"《Notice.》 [{q.skill}] — no last thought heard. Skipped, not invented.")
            continue
        tags = list(q.tags)
        if q.node_type is NodeType.CONSTRAINT:
            tags += act_tags(text)
        # the skill name is the last tag so `acquired` can read it back
        tags.append(q.skill)
        node = MemoryNode(type=q.node_type, content=text, tags=tags, links=[])
        node.write(path / folder_for(q.node_type) / f"{node.id}.md")
        nodes.append(node)
        kind = "Skill" if q.node_type is NodeType.CONSTRAINT else "Knowledge"
        voice(f"《Confirmed.》 {kind} [{q.skill}] acquired.")

    # the birth is the first episode — remembered, dated, linked to everything it created
    born = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    who = persona.name if persona else "the assistant"
    episode = MemoryNode(
        type=NodeType.EPISODE,
        content=f"Reincarnated {born}: {who} woke with {len(nodes)} skill(s)"
                + (f"; skipped {', '.join(skipped)}" if skipped else "") + ".",
        tags=["reincarnation", "birth"],
        links=[n.id for n in nodes],
    )
    episode.write(path / folder_for(NodeType.EPISODE) / f"{episode.id}.md")
    nodes_all = nodes + [episode]

    with Storage(default_db_path(path)) as storage:
        for n in nodes_all:
            storage.upsert_node(n)
        if nodes:
            storage.increment_edges([n.id for n in nodes])

    (path / "README.md").write_text(
        "# Your all41n14lla vault\n\n"
        "Born by reincarnation. Four folders, four types of memory:\n\n"
        "- `concepts/` — stable ideas\n- `patterns/` — repeated behaviors\n"
        "- `episodes/` — specific events\n- `constraints/` — hard rules\n\n"
        "Every file here came from an answer you typed. Nothing was read from your disk.\n",
        encoding="utf-8",
    )

    voice("《Confirmed.》 Extra skill [Predator] available. Nothing is devoured without consent — "
          "`all41n14lla devour <path>` when you choose what it may eat.")
    voice(f"《Report.》 You wake in a cave. It is dark. {who} is online.")
    voice(f"Vault: {path} · {len(nodes_all)} memories. Next: `all41n14lla wire` connects {who} to every AI on this machine.")

    return Rebirth(vault=path, persona=persona, nodes=nodes_all, skipped=skipped, transcript=lines)


def load_answers(file: Path) -> dict[str, str]:
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("answers file must be a JSON object of question-key → text")
    return {k: str(v) for k, v in data.items()}
