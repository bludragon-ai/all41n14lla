# Architecture

How `all41n14lla` actually works.

## Four node types

Every memory is one of four types. Each has its own folder under the vault root and its own retrieval policy.

| Type         | Holds                              | Folder          |
| ------------ | ---------------------------------- | --------------- |
| `concept`    | Stable ideas. Long-lived facts.    | `concepts/`     |
| `pattern`    | Repeated behaviors. Heuristics.    | `patterns/`     |
| `episode`    | Specific events. Time-bound.       | `episodes/`     |
| `constraint` | Hard rules. Must-not-violate.      | `constraints/`  |

The type is not cosmetic. It controls how the node is ranked at recall time (see Retrieval flow below).

## Storage

Markdown files on disk are canonical. SQLite is an index.

- Source of truth: markdown files under `<vault>/{concepts,patterns,episodes,constraints}/`.
- Index: `<vault>/.all41n14lla/index.db` — SQLite, derived from the markdown. Delete it and it rebuilds.
- Full-text search: an FTS5 virtual table `nodes_fts` indexes `content` and `tags` with the Porter tokenizer.
- Edges: an `edges` table tracks co-occurrence between concept IDs. One row per directed pair with a `weight` counter.

A user can edit a markdown file by hand. The `watchdog` observer picks up the change and reconciles the index. Hand-editing is a supported workflow, not a workaround.

## Frontmatter schema

Every node is a markdown file with YAML frontmatter:

```yaml
---
id: 7c2f1e4b-9a3d-4e11-bd2c-1f6a4c8e9d55
type: concept          # concept | pattern | episode | constraint
tags: [python, sqlite]
links: [b1a2c3d4-...]  # other node IDs
created: 2026-04-23T14:02:11+00:00
updated: 2026-04-23T14:02:11+00:00
stale: false
decay: 0.0
---
Body content goes here. Plain markdown.
```

The dataclass is `MemoryNode` in `engine/nodes.py`. `from_file()` parses the frontmatter; `to_markdown()` writes it back. Edits round-trip without loss.

## Retrieval flow

A `recall` query runs in three stages:

1. The query is matched against `nodes_fts` via FTS5 `MATCH`. This yields a BM25-ranked candidate set across all types.
2. Candidates are bucketed by type and re-ranked per-type.
3. Results are merged and returned.

Per-type policies:

- **Concept** — match score plus tag overlap. No recency boost.
- **Pattern** — match score plus recency, with a moderate recency boost. Recent patterns beat older ones at similar relevance.
- **Episode** — match score plus recency, with a stronger recency boost than patterns. Old episodes decay fast.
- **Constraint** — any constraint whose tags overlap the query's tags is **always** returned, regardless of match score. Hard rules are not allowed to silently drop out of a recall.

## Pathways

On `episode` write, the engine extracts referenced concept IDs from the node's `links` field and from concept mentions in the body. For each co-occurring pair of concepts, `edges.weight` is incremented.

This turns episodes into a weighting signal over the concept graph. Concepts that repeatedly co-occur in lived episodes accumulate weight together.

`consolidate` (v0.2) walks the edges table, finds edge-dense clusters of concepts, and promotes each cluster to a new `pattern` node. Decay runs in the same pass: stale edges lose weight over time, so patterns reflect *current* behavior, not everything that ever happened.

## MCP server

Transport: stdio, via the `mcp` Python SDK. One process, one client.

Five tools exposed:

- `remember` — write a new node.
- `recall` — search.
- `forget` — delete by ID.
- `inspect` — show a node plus its neighbors in the edge graph.
- `consolidate` — run pattern promotion and decay.

Each tool's description is written like marketing copy for the calling model. The description is what the LLM reads when deciding whether to pick the tool, so it is treated as a prompt, not a comment. Bad descriptions lead to bad tool selection.

## Concurrency

- SQLite runs in WAL mode. Many readers, one writer.
- The watchdog observer reconciles manual file edits into the index.
- No inter-process locking. `all41n14lla` is built for a single local process (one MCP server, one CLI user). Running two writers against the same vault is not supported.

## What ships when

- `0.1.0-alpha` (current): scaffold. Frontmatter + `MemoryNode` dataclass are implemented. CLI commands are stubs.
- `0.1.0`: storage, FTS5 retrieval, MCP server, watchdog reconciliation.
- `0.2.0`: pathway promotion and decay.
