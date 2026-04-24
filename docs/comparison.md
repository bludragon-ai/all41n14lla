# Comparison

Honest look at `all41n14lla` vs. the other MCP-memory tools worth naming. Every competitor claim below was verified against the tool's current README or docs. Anything unverified is marked.

## Matrix

| Tool                           | Markdown-native | Typed retrieval (4 node types) | User-owned local vault | Offline-first | MCP-native | Embeddings | License    |
| ------------------------------ | --------------- | ------------------------------ | ---------------------- | ------------- | ---------- | ---------- | ---------- |
| **all41n14lla**                | Yes             | Yes (concept/pattern/episode/constraint) | Yes          | Yes           | Yes        | No (v0.1)  | MIT        |
| **Basic Memory**               | Yes             | Partial (observations + relations, not 4 fixed types) | Yes (local-first; optional paid cloud sync) | Yes | Yes | Yes (FastEmbed, hybrid FTS + vector) | AGPL-3.0 |
| **MemPalace**                  | No (verbatim text + SQLite + ChromaDB) | Partial (wings/rooms/drawers hierarchy) | Yes | Yes       | Yes        | Yes (local, ChromaDB default) | MIT |
| **mem0**                       | No (pluggable vector DB) | Partial (user/session/agent levels) | Only in library mode; cloud and self-hosted are the pitched paths | Library mode only | No (not MCP-native; LangGraph/CrewAI integrations) | Yes (OpenAI `text-embedding-3-small` default) | Apache-2.0 |
| **MCP Memory (reference)**     | No (JSONL file) | No (user-defined entity types, no enforced taxonomy) | Yes (local JSONL) | Yes | Yes | No (text search only) | MIT |

## Notes per tool

**all41n14lla.** Markdown on disk is the source of truth. SQLite with FTS5 is just an index. Four fixed node types, each with its own ranking policy; constraints are never silently dropped from a recall. Weakness: no embeddings in v0.1, keyword search only. No cloud sync. No web UI. No benchmarks yet.

**Basic Memory.** The closest philosophical neighbor. Also markdown-first, also MCP-native, also local-first. Adds semantic search via FastEmbed, which `all41n14lla` does not. Uses observations + relations rather than fixed node types. AGPL-3.0 license is more restrictive than MIT and may matter for commercial consumers.

**MemPalace.** Different shape. Stores verbatim text and retrieves it with vector search over ChromaDB. Organizes into a wings/rooms/drawers hierarchy rather than node types. Ships 29 MCP tools. Claims 96.6% R@5 on LongMemEval with no API calls. Strong benchmark story. Not markdown-native — hand-editing a memory is not the primary workflow.

**mem0.** Not MCP-native (as of this writing). Pitched at LangGraph / CrewAI agent frameworks with a hosted cloud product as the default path. Uses embeddings and hybrid search. If you want a managed memory service with a cloud dashboard, mem0 is that. If you want a file you can `cat`, it isn't.

**MCP Memory reference server.** The official reference implementation from the modelcontextprotocol org. JSONL on disk, text search, no embeddings, no fixed taxonomy. Good for understanding the MCP protocol. Thin on features compared to any of the above.

## When to use which

- **Use `all41n14lla`** if you want to open your memories in Obsidian, edit them in vim, diff them in git, and have constraints that are guaranteed to surface on every relevant recall. You are fine with keyword search in v0.1.
- **Use Basic Memory** if you want the same markdown-first posture plus semantic search today, and the AGPL license is acceptable.
- **Use MemPalace** if your bottleneck is recall quality on long conversation histories and you are happy with a vector-store-backed palace metaphor instead of plain files.
