# all41n14lla

Portable memory for AI agents. Markdown on your disk. Speaks MCP.

> **Status:** `v0.1.0a1` (alpha). The engine is real: SQLite + FTS5 index, MCP stdio server, four-type storage, watchdog reconciliation. 16/16 tests passing. A short demo video lands with v0.1.0 (non-alpha) after a 24-hour bake. Expect rough edges until then.

## The problem

Agent memory is broken in five specific ways: models forget mid-session, hosted memory stores trap your data, memory does not cross agents, most stores are opaque blobs you cannot audit, and nothing works offline. The dominant "fix" — jam more context into the prompt — treats the language model as a storage engine. It is not one. It is a reasoning engine. Storage belongs on disk.

## What this fixes

Memory should live where you can read it, back it up, grep it, diff it in git, and open it in a text editor. It should speak a protocol every MCP-capable client already supports, so swapping agents does not mean rebuilding your memory. It should be typed, because different kinds of memory deserve different retrieval policies.

`all41n14lla` stores memories as markdown files on your disk, indexes them locally with SQLite + FTS5, and exposes them over MCP stdio. Claude Code, Claude Desktop, Cursor, and anything else that speaks MCP gets `remember`, `recall`, `forget`, `inspect`, and `consolidate` for free. No SDK lock-in. No vendor cloud. No round trip. Your vault is yours.

## How it works

Four node types, one vault, type-aware retrieval.

- **Concepts** — stable ideas and definitions. Long-lived. Surfaced when their topic comes up.
- **Patterns** — repeated behaviors. Derived from episodes, not written directly. Promoted when the repetition crosses a threshold.
- **Episodes** — specific events. High volume. Decay fast, because most stop mattering once the situation is over.
- **Constraints** — hard rules. Never decay. Always surfaced when their tags overlap the query. Non-negotiable.

Each lives in its own folder (`concepts/`, `patterns/`, `episodes/`, `constraints/`). Each is a markdown file with YAML frontmatter. You can edit them by hand — the `watchdog` observer reconciles changes into the index. Hand-editing is a supported workflow, not a workaround.

Retrieval is not one ranking function over one bucket. Concepts rank by match score plus tag overlap. Patterns add a moderate recency boost. Episodes add a stronger one. Constraints whose tags overlap the query are **always** returned, regardless of match score — hard rules are not allowed to silently drop out of a recall. Full architecture: [docs/architecture.md](docs/architecture.md).

## Install

### From PyPI (coming soon)

```bash
pipx install all41n14lla
```

Not published yet. Install from source in the meantime.

### From source (works now)

```bash
git clone https://github.com/bludragon-ai/all41n14lla.git
cd all41n14lla
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11+ works; 3.13 is what I develop against.

## First run

```bash
all41n14lla init                                   # scaffolds ~/.all41n14lla/ (hidden dotfile vault)
all41n14lla remember concept "sqlite fts5 uses the porter tokenizer by default"
all41n14lla recall "sqlite tokenizer"
all41n14lla doctor                                 # verify environment + vault health
```

The default vault is `~/.all41n14lla/` — a hidden per-user dotfile. Pass `--path ~/memory` (or any other path) if you prefer a visible vault, e.g. one you open in Obsidian.

Other commands: `forget <id>`, `reconcile` (rebuild the index from disk), `inspect <query>` (stub in v0.1-alpha, full in v0.1 final), `consolidate` (stub, lands in v0.2), `version`, `serve`.

## Claude Code / Claude Desktop / Cursor config

Drop this into the MCP config for your client of choice.

```json
{
  "mcpServers": {
    "all41n14lla": {
      "command": "all41n14lla",
      "args": ["serve"]
    }
  }
}
```

Transport is stdio. One process, one client. The server exposes `remember`, `recall`, `forget`, `inspect`, and `consolidate` as MCP tools.

## Comparison

Every claim below was verified against the tool's current README or docs at the time of writing.

| Tool                           | Markdown-native | Typed retrieval (4 node types) | User-owned local vault | Offline-first | MCP-native | Embeddings | License    |
| ------------------------------ | --------------- | ------------------------------ | ---------------------- | ------------- | ---------- | ---------- | ---------- |
| **all41n14lla**                | Yes             | Yes (concept/pattern/episode/constraint) | Yes          | Yes           | Yes        | No (v0.1)  | MIT        |
| **Basic Memory**               | Yes             | Partial (observations + relations, not 4 fixed types) | Yes (local-first; optional paid cloud sync) | Yes | Yes | Yes (FastEmbed, hybrid FTS + vector) | AGPL-3.0 |
| **MemPalace**                  | No (verbatim text + SQLite + ChromaDB) | Partial (wings/rooms/drawers hierarchy) | Yes | Yes       | Yes        | Yes (local, ChromaDB default) | MIT |
| **mem0**                       | No (pluggable vector DB) | Partial (user/session/agent levels) | Only in library mode; cloud and self-hosted are the pitched paths | Library mode only | No (not MCP-native; LangGraph/CrewAI integrations) | Yes (OpenAI `text-embedding-3-small` default) | Apache-2.0 |
| **MCP Memory (reference)**     | No (JSONL file) | No (user-defined entity types, no enforced taxonomy) | Yes (local JSONL) | Yes | Yes | No (text search only) | MIT |

Read the full comparison in [docs/comparison.md](docs/comparison.md).

## Roadmap

- **v0.1 (this release)** — four node types, markdown on disk, SQLite + FTS5 index, MCP stdio server, watchdog reconciliation, CLI (`init`, `serve`, `doctor`, `remember`, `recall`, `forget`, `reconcile`, `version`). Lexical search only.
- **v0.2** — embedding-based semantic recall, pattern promotion from repeated episodes, decay on episodes, scheduled `consolidate` pass.
- **v0.3** — Obsidian plugin so the vault is a first-class notebook, graph view for nodes and links, bidirectional editing.

No dates. Ships when it ships.

## Docs

- [Why](docs/why.md) — the thesis: what is broken about agent memory and why this shape fixes it.
- [Savant cognition as memory architecture](docs/savant-cognition.md) — the longer origin story. How a personal interest in typed, pattern-indexed, never-degrading memory became the shape of this project, grounded in a survey of 60+ existing agent-memory tools.
- [Architecture](docs/architecture.md) — how the engine actually works. Storage, frontmatter schema, retrieval flow, pathways, MCP surface.
- [Comparison](docs/comparison.md) — honest look at `all41n14lla` vs. Basic Memory, MemPalace, mem0, and the MCP reference server.
- [Origin](ORIGIN.md) — where the name comes from.

## License

MIT. Copyright Jordan Truong.

Open-source inspirations visible in the style of this project: [santifer/career-ops](https://github.com/santifer/career-ops) and [cv-santiago](https://github.com/santifer/cv-santiago) — both good examples of useful, personal, no-fluff tooling.
