# Comparison

Honest look at `all41n14lla` vs. the other MCP-memory tools worth naming. Every competitor claim below was verified against the tool's current README or docs. Anything unverified is marked.

## Matrix

| Tool                           | Markdown-native | Typed retrieval (4 node types) | Deterministic constraint surfacing | User-owned local vault | Offline-first | MCP-native | Embeddings | License    |
| ------------------------------ | --------------- | ------------------------------ | ---------------------------------- | ---------------------- | ------------- | ---------- | ---------- | ---------- |
| **all41n14lla**                | Yes             | Yes (concept/pattern/episode/constraint) | **Yes** (uncapped floor path; tag-scoped) | Yes          | Yes           | Yes        | No (deliberate — see README roadmap)  | MIT        |
| **Basic Memory**               | Yes             | Partial (observations + relations, not 4 fixed types) | No (ranked retrieval only) | Yes (local-first; optional paid cloud sync) | Yes | Yes | Yes (FastEmbed, hybrid FTS + vector) | AGPL-3.0 |
| **MemPalace**                  | No (verbatim text + SQLite + ChromaDB) | Partial (wings/rooms/drawers hierarchy) | No (vector ranking) | Yes | Yes       | Yes        | Yes (local, ChromaDB default) | MIT |
| **mem0**                       | No (pluggable vector DB) | Partial (user/session/agent levels) | No (similarity ranking) | Only in library mode; cloud and self-hosted are the pitched paths | Library mode only | No (not MCP-native; LangGraph/CrewAI integrations) | Yes (OpenAI `text-embedding-3-small` default) | Apache-2.0 |
| **MCP Memory (reference)**     | No (JSONL file) | No (user-defined entity types, no enforced taxonomy) | No (text search) | Yes (local JSONL) | Yes | Yes | No (text search only) | MIT |

## Notes per tool

**all41n14lla.** Markdown on disk is the source of truth. SQLite with FTS5 is just an index. Four fixed node types, each with its own ranking policy; constraints whose tags overlap the query ride a separate, uncapped code path and are never silently dropped from a recall — deterministic context injection, not a ranking (see the benchmark below). Weakness: no embeddings (deliberate), lexical phrase search for non-constraints. No cloud sync. No web UI.

**Basic Memory.** The closest philosophical neighbor. Also markdown-first, also MCP-native, also local-first. Adds semantic search via FastEmbed, which `all41n14lla` does not. Uses observations + relations rather than fixed node types. AGPL-3.0 license is more restrictive than MIT and may matter for commercial consumers.

**MemPalace.** Different shape. Stores verbatim text and retrieves it with vector search over ChromaDB. Organizes into a wings/rooms/drawers hierarchy rather than node types. Ships 29 MCP tools. Claims 96.6% R@5 on LongMemEval with no API calls. Strong benchmark story. Not markdown-native — hand-editing a memory is not the primary workflow.

**mem0.** Not MCP-native (as of this writing). Pitched at LangGraph / CrewAI agent frameworks with a hosted cloud product as the default path. Uses embeddings and hybrid search. If you want a managed memory service with a cloud dashboard, mem0 is that. If you want a file you can `cat`, it isn't.

**MCP Memory reference server.** The official reference implementation from the modelcontextprotocol org. JSONL on disk, text search, no embeddings, no fixed taxonomy. Good for understanding the MCP protocol. Thin on features compared to any of the above.

## Benchmark — constraint recall under noise

The one number this project optimizes for: **when a hard rule is buried under
operational noise, does a recall for the situation surface the rule in the top 5?**

20 scenarios across common ops domains (deploys, secrets, migrations, billing,
PII, on-call, …). Each seeds a fresh throwaway vault with one tagged constraint
plus 50 noise episodes that talk the way standups actually talk (the query
phrasing appears verbatim in the noise). In 4 of 20 scenarios the rule's own
text also contains the query phrase, so plain BM25 gets honest lexical chances.

Measured (seed 41, reproducible):

| Retrieval                              | constraint recall@5 |
| -------------------------------------- | ------------------- |
| pure BM25 phrase match (v0.1 behavior) | **1/20 (5%)**       |
| deterministic constraint floor         | **20/20 (100%)**    |

The floor's 100% is *by construction* — every scenario's rule is tagged and
every query overlaps those tags, so the separate code path cannot miss. That
is the claim, exactly: deterministic, disclosed precondition, no ranking
involved. The baseline's 5% is *measured*, not invented — even the four rules
containing the query phrase mostly drowned, because fifty noise episodes
contain it too and a top-5 cutoff does what cutoffs do.

Reproduce it:

```bash
.venv/bin/python benchmarks/constraint_recall.py
```

## When to use which

- **Use `all41n14lla`** if you want to open your memories in Obsidian, edit them in vim, diff them in git, and have constraints that are guaranteed to surface on every relevant recall. You are fine with keyword search in v0.1.
- **Use Basic Memory** if you want the same markdown-first posture plus semantic search today, and the AGPL license is acceptable.
- **Use MemPalace** if your bottleneck is recall quality on long conversation histories and you are happy with a vector-store-backed palace metaphor instead of plain files.
