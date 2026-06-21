# all41n14lla

Portable memory for AI agents. Markdown on your disk. Speaks MCP.

[![Tests](https://github.com/bludragon-ai/all41n14lla/actions/workflows/test.yml/badge.svg)](https://github.com/bludragon-ai/all41n14lla/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/all41n14lla.svg)](https://pypi.org/project/all41n14lla/)
[![Python](https://img.shields.io/pypi/pyversions/all41n14lla.svg)](https://pypi.org/project/all41n14lla/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Status:** `v0.1.0` (stable, on PyPI) + type-aware retrieval and `wire` landed in main (unreleased). The engine is real: SQLite + FTS5 index, MCP stdio server, four-type storage, live watchdog reconciliation, deterministic constraint floor on recall. The full pytest suite passes in CI on Python 3.11–3.14 (no hard-coded count here — counts drift; CI is the source of truth). Install from PyPI below.

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

Retrieval is not one ranking function over one bucket. Concepts rank by match score plus tag overlap. Patterns add a moderate recency boost. Episodes add a stronger one (30-day half-life decay). Constraints whose tags overlap the query are **always** returned, regardless of match score — hard rules are not allowed to silently drop out of a recall.

The constraint guarantee is **deterministic context injection, not a ranking**: a separate, uncapped code path keyed on tag overlap (stem-aware), exempt from the result limit, returned in the top slots. Stated precondition: it is tag-scoped — an untagged constraint, or a query with no overlapping terms, will not trigger it. `all41n14lla doctor` reports untagged constraints and tag hotspots so the precondition is observable, not a gotcha. The floor caps at 50 injected rules to protect the caller's context window. Full architecture: [docs/architecture.md](docs/architecture.md).

## Install

One command — install, create the vault, wire every MCP client you have:

```bash
pipx install all41n14lla && all41n14lla init && all41n14lla wire
```

The same thing as three readable steps:

1. **Install** — `pipx install all41n14lla` (verify: `all41n14lla version`)
2. **Create the vault** — `all41n14lla init` (scaffolds `~/.all41n14lla/`)
3. **Wire your clients** — `all41n14lla wire` detects Claude Code, Claude Desktop, Cursor, Gemini CLI, and Codex CLI and adds the server to each config. Idempotent, backs up any config it touches, `--dry-run` previews without writing.

> `wire` is in main, unreleased — on the released `0.1.0` wheel, paste the config block from [Client config](#client-config) instead.

Python 3.11+ works; 3.13 is what I develop against. Working from a clone? See [CONTRIBUTING.md](CONTRIBUTING.md#getting-set-up).

## First run

```bash
all41n14lla init                                   # scaffolds ~/.all41n14lla/ (hidden dotfile vault)
all41n14lla remember concept "sqlite fts5 uses the porter tokenizer by default"
all41n14lla recall "sqlite tokenizer"
all41n14lla doctor                                 # verify environment + vault health
```

The default vault is `~/.all41n14lla/` — a hidden per-user dotfile. Pass `--path ~/memory` (or any other path) if you prefer a visible vault, e.g. one you open in Obsidian. Every CLI command also honors `ALL41N14LLA_VAULT`, so run `export ALL41N14LLA_VAULT=~/memory` once and you can drop `--vault` from each call — the MCP server reads the same variable, so the CLI and the server always agree.

Other commands: `forget <id>`, `reconcile` (rebuild the index from disk), `inspect <query>` (node details + co-occurrence neighbors), `consolidate` (stub, lands in v0.2), `wire` (auto-configure MCP clients), `version`, `serve`.

## Client config

`all41n14lla wire` writes all of this for you (and `wire --dry-run` shows you exactly what it would write). To wire a client by hand instead, this is the shape.

**JSON clients** — Claude Code (`~/.claude.json`), Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS), Cursor (`~/.cursor/mcp.json`), and Gemini CLI (`~/.gemini/settings.json`) all take the same block under the `mcpServers` key:

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

**Codex CLI** (`~/.codex/config.toml`) uses TOML — note the underscore in `mcp_servers`:

```toml
[mcp_servers.all41n14lla]
command = "all41n14lla"
args = ["serve"]
```

Using a non-default vault? Add an env entry — `"env": {"ALL41N14LLA_VAULT": "/path/to/vault"}` in JSON, or an `[mcp_servers.all41n14lla.env]` table with `ALL41N14LLA_VAULT = "/path/to/vault"` in TOML. If a client launches with a restricted PATH (Claude Desktop does), use the absolute binary path from `which all41n14lla` as `command` — `wire` does this automatically.

Transport is stdio. One process, one client. The server exposes `remember`, `recall`, `forget`, `inspect`, and `consolidate` as MCP tools.

## Comparison

Every claim below was verified against the tool's current README or docs at the time of writing.

| Tool                           | Markdown-native | Typed retrieval (4 node types) | Deterministic constraint surfacing | User-owned local vault | Offline-first | MCP-native | Embeddings | License    |
| ------------------------------ | --------------- | ------------------------------ | ---------------------------------- | ---------------------- | ------------- | ---------- | ---------- | ---------- |
| **all41n14lla**                | Yes             | Yes (concept/pattern/episode/constraint) | **Yes** — measured 20/20 vs BM25's 1/20 ([benchmark](docs/comparison.md#benchmark--constraint-recall-under-noise)) | Yes          | Yes           | Yes        | No (deliberate)  | MIT        |
| **Basic Memory**               | Yes             | Partial (observations + relations, not 4 fixed types) | No (ranked retrieval only) | Yes (local-first; optional paid cloud sync) | Yes | Yes | Yes (FastEmbed, hybrid FTS + vector) | AGPL-3.0 |
| **MemPalace**                  | No (verbatim text + SQLite + ChromaDB) | Partial (wings/rooms/drawers hierarchy) | No (vector ranking) | Yes | Yes       | Yes        | Yes (local, ChromaDB default) | MIT |
| **mem0**                       | No (pluggable vector DB) | Partial (user/session/agent levels) | No (similarity ranking) | Only in library mode; cloud and self-hosted are the pitched paths | Library mode only | No (not MCP-native; LangGraph/CrewAI integrations) | Yes (OpenAI `text-embedding-3-small` default) | Apache-2.0 |
| **MCP Memory (reference)**     | No (JSONL file) | No (user-defined entity types, no enforced taxonomy) | No (text search) | Yes (local JSONL) | Yes | Yes | No (text search only) | MIT |

Read the full comparison in [docs/comparison.md](docs/comparison.md).

## Roadmap

- **v0.1 (shipped)** — four node types, markdown on disk, SQLite + FTS5 index, MCP stdio server, watchdog reconciliation, CLI (`init`, `serve`, `doctor`, `remember`, `recall`, `forget`, `reconcile`, `version`). Lexical search only.
- **v0.2 (in main, unreleased)** — type-aware retrieval: the deterministic constraint floor, per-type rescoring with tag-overlap bonus, 30-day-half-life episode decay, `doctor` floor diagnostics. Pattern promotion (`consolidate`) remains a stub — honestly: the co-occurrence signal it needs (the `edges` table) only fills when episodes carry explicit `links`, and a body-mention extractor does not exist yet.
- **v0.3** — pattern promotion over a real co-occurrence signal + tag-scoped recall (`tags=[...]` filter) for multi-team shared-memory use.
- **Explicitly not planned** — embedding/vector recall as a hard dependency (see [docs/comparison.md](docs/comparison.md)); may appear later as an off-by-default opt-in. No Obsidian plugin, graph view, or bidirectional-edit subsystem — the vault is plain markdown and already opens anywhere.

No dates. Ships when it ships.

## Docs

- [Why](docs/why.md) — the thesis: what is broken about agent memory and why this shape fixes it.
- [Savant cognition as memory architecture](docs/savant-cognition.md) — the longer origin story. How a personal interest in typed, pattern-indexed, never-degrading memory became the shape of this project, grounded in a survey of 60+ existing agent-memory tools.
- [Architecture](docs/architecture.md) — how the engine actually works. Storage, frontmatter schema, retrieval flow, pathways, MCP surface.
- [Comparison](docs/comparison.md) — honest look at `all41n14lla` vs. Basic Memory, MemPalace, mem0, and the MCP reference server.
- [Origin](ORIGIN.md) — where the name comes from.
- [Quickstart — Claude Desktop](docs/quickstart-claude-desktop.md) — five-minute install-to-working guide for Claude Desktop users.

## License

MIT. Copyright Jordan Truong.

Open-source inspirations visible in the style of this project: [santifer/career-ops](https://github.com/santifer/career-ops) and [cv-santiago](https://github.com/santifer/cv-santiago) — both good examples of useful, personal, no-fluff tooling.
