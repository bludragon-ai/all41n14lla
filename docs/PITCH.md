# What is all41n14lla? (the say-it-out-loud card)

## 10 seconds
Every AI you use forgets you. all41n14lla is a memory that lives on **your** disk as plain markdown —
and every AI you use reads and writes the **same one**. The chatbot is a face. This is the brain.

## 30 seconds
It's not a harness and not a chatbot — it's the memory layer underneath them. Memories are markdown
files on your machine: you can read them, grep them, edit them, put them in git. An MCP server exposes
`remember` / `recall` / `forget` / `inspect` / `consolidate`, so Claude, Cursor, local models — anything
MCP — share one brain. Swap the model, keep the mind. And it's built like a brain: a **left hemisphere**
that records exactly what happened, and (v0.2) a **right hemisphere** that remembers what things meant —
they check each other, so the memory notices when it disagrees with itself.

## 2 minutes — what makes it different from every other memory tool
1. **Files, not blobs.** mem0/Zep/hosted stores keep your memory in their database or cloud. Here it's
   human-legible markdown you own — auditable, diffable, backupable, deletable. No vendor, no lock-in.
2. **Harness-agnostic by protocol.** It speaks MCP stdio, so it isn't married to one framework or SDK.
   One memory pool across every agent you run — today and whatever ships next year.
3. **Offline-first, $0 to run.** SQLite + FTS5 locally; no round-trips, no API bill, works on a plane.
4. **Typed memory, deterministic floor.** Different kinds of memory get different retrieval policies,
   and hard constraints can't be displaced by fuzzy similarity.
5. **The two-brain roadmap.** Literal + associative recall that cross-audit each other — disagreement
   between the hemispheres is surfaced as drift, not silently ranked away. (docs/TWO-BRAINS.md)
6. **Lived-in, not a demo.** It has run a real person's daily operation across multiple machines and
   harnesses for months. Its own build-log is stored in itself.

## One-liners for specific rooms
- **To a recruiter:** "Portable memory for AI agents — local-first MCP server on PyPI; I run my whole
  multi-agent setup on it."
- **To a dev:** "Markdown-backed MCP memory: FTS5 recall with a deterministic constraint floor;
  embedding hemisphere landing in v0.2."
- **To your aunt:** "It's how my AI remembers me — and it's a folder on my computer, not somebody's cloud."
