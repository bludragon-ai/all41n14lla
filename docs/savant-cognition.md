# Savant cognition as memory architecture

How a personal interest in a specific kind of memory became the shape of this project.

## The question

I kept hitting the same wall. Every AI tool I used had its own memory layer, and none of them talked to each other. Claude forgot on Monday what Cursor knew on Friday. A new session with any of them started from zero. The moment I switched models, the thread of what I was working on broke. I was the only stable identity across all of it, and I was the one doing the remembering by hand — re-pasting context, re-explaining constraints, re-establishing what "my stack" even means this week.

The obvious first instinct was to fix it with a better database. Bigger vector store. Cleverer embeddings. Longer context window. But after a while I started to ask a different question, because every fix that pointed at the database felt like it was solving the wrong layer. Is there a model for what good memory should actually look like? Not a faster lookup — a better architecture. Something that knows the difference between a fact you want to keep forever and a debugging session that stopped mattering six hours after it ended.

## LLMs are not memory systems

A context window is working memory. It is volatile, it is bounded, and it evicts the things you needed as soon as you push in the things you are working on now. Treating it as long-term storage is the same category mistake as treating RAM as a hard drive. It happens to work for small tasks because the workload fits. It does not work for anything that needs to persist past the session.

Tokens are also a bad substrate for long-term facts. You pay linearly for every token the model has to carry, and the information density inside a context window drops as you fill it — you get worse retrieval the more you cram in, not better. So the "just make the window bigger" answer is expensive and it degrades the exact property you were trying to buy. Meanwhile, embedding-based stores have the opposite problem: they flatten everything into a single semantic-similarity space. That is fine when memory really is fuzzy, but not all memory is fuzzy. A hard rule like "never commit with `--no-verify`" is not a vibe. A stable definition of a system component is not a neighborhood in embedding space. Treating everything as "find me stuff that sounds like this" throws away the structure that makes certain memories useful.

The reframe that made the rest of the design fall out was separating the reasoning engine from the memory system. The LLM thinks. A dedicated memory layer remembers. This is what the REMem paper calls out explicitly — episodic memory is not just a storage trick bolted onto an agent, it is a reasoning primitive. If you want agents that behave coherently across sessions, they need an external memory they can query, write to, and trust to give them the right shape of thing back. Storage belongs on disk. Reasoning belongs in the model. The seam between them is a protocol.

## Why savant cognition — and what that means honestly

I have long been interested in savant cognition. Not professionally, not academically — as a personal fascination. The thing that draws me in is that savants have the kind of memory LLMs conspicuously do not: narrow but perfect, pattern-indexed, never degrading. You show a savant a city skyline once and they draw it back from memory a decade later. They do not compress it into a fuzzy gist. They hold it as a typed, structured thing, and it stays intact. That is the property I kept wanting from my tools.

I want to be honest about the scope of that interest. I am not quoting savant-cognition academic literature in this doc. My fascination is personal and it shapes intuition — the intuition that memory can be *typed*, *pattern-indexed*, and *durable* rather than a single flat blob — not my citations. The concrete architectural choices in `all41n14lla` come from surveying the agent-memory tools that already exist and noticing what they collectively got right and where the shape was still missing. That survey is what the rest of this document is about.

## What the survey actually said

I kept a NotebookLM corpus of 60-plus agent-memory tools while I was thinking through this. Reading across them, four findings kept repeating. Each one ended up translating into a design choice.

### Finding 1: Typed memory works better than flat memory

The serious tools do not treat memory as a single undifferentiated pile. Letta, which carries the MemGPT lineage, organizes agent memory into **memory blocks** — distinct, typed slots for different kinds of context (persona, human, archival). Mem0 splits memory by scope — **user, session, and agent** — so a fact about the user persists across sessions while session-scoped state does not bleed between conversations. The specific axes differ, but the principle is the same: a useful memory system has structure, and the structure exists because different kinds of memory want different retrieval behavior.

The `all41n14lla` translation is four explicit node types — **concept, pattern, episode, constraint** — each with its own retrieval policy. Concepts rank by match score plus tag overlap. Patterns add a moderate recency boost. Episodes add a stronger one because old events rot fast. Constraints are guaranteed to surface whenever their tags overlap a query, regardless of match score, because a hard rule silently dropping out of a recall is the failure mode that bothered me most about flat stores. Full retrieval policy in `docs/architecture.md`. Letta went further than most on typing the substrate; I took that seriously and picked a specific taxonomy instead of leaving it user-defined.

### Finding 2: Graph-backed memory is powerful but heavy

Several tools already show that a graph-shaped memory layer works. The memory-graph project is the cleanest example — an MCP memory server backed by a graph database, with nodes and edges as first-class citizens. Graphiti and a handful of similar projects extend that idea toward temporal knowledge graphs for agents. The pattern is legitimate and the results are good. The cost is that you bring a graph database into the stack, and now you have operational weight — another service, another schema, another thing to back up and version and reason about.

The `all41n14lla` translation keeps the graph intuition and drops the graph database. The substrate is markdown on disk indexed by SQLite with an FTS5 virtual table for full-text search. Edges live in a plain SQLite table — one row per directed concept pair, one integer weight column — acting as a lightweight **pathways** layer. Every time an episode is written, the engine walks the concept IDs it references and increments the co-occurrence weight between each pair. You get graph-like behavior (concepts that repeatedly appear together accumulate weight together) without the operational weight of standing up a graph DB. Embeddings are deferred to v0.2 on purpose — ship the shape first, then add the dynamics.

### Finding 3: Pattern-indexed retrieval beats keyword matching

This is the finding that maps most directly onto the savant intuition. Sean Pedersen's write-up on **Sparse Distributed Representations**, in the Hawkins/Numenta tradition, frames memory as organized by *pattern overlap* rather than exact match. Two items that share a lot of active bits are treated as related, even if they do not share any specific keyword. That is closer to how savants appear to work — they do not keyword-search their memory, they find the shape that overlaps the current input and pull the whole pattern forward with it.

The `all41n14lla` translation is the pathways graph plus the future `consolidate` pass. Every episode write increments co-occurrence weights between the concepts it mentions. Over time, concepts that keep showing up together build up edges. In v0.2, the `consolidate` pass walks the edges table, finds edge-dense clusters, and promotes each cluster into a new `pattern` node — with decay running in the same pass so that stale co-occurrence loses weight over time. The system learns which ideas actually belong together based on how they get used, not by being told up front. That is the pattern-indexed posture, implemented inside a SQLite table instead of a biological cortex.

### Finding 4: Memory needs to persist where the user can audit it

This is the thing almost every existing tool gets wrong, and it is the thing that made me irritable enough to start building. Most memory stores are opaque. A vector DB is a pile of floats. A hosted cloud store is a proprietary export format. Even the MCP reference memory server, which is the simplest entry point, persists as JSONL — technically on your disk, but not something you would open in an editor and read through. When the agent writes down something about you, you cannot see it, you cannot grep it, you cannot correct it, and you cannot take it with you when you switch tools.

The `all41n14lla` translation is boring on purpose: **markdown files on disk**. YAML frontmatter for the structured fields (id, type, tags, links, timestamps, decay). Body is plain markdown. You can `grep` it, `git diff` it, edit it in Obsidian, back it up with Syncthing, commit it to a private repo. The source of truth is the files; SQLite is just an index you can delete and rebuild. If a human edits a file by hand, the watchdog observer picks up the change and reconciles it. Hand-editing is a supported workflow, not a workaround. Your vault is yours.

## What v0.1 has vs. v0.2+

I want to be precise about what is shipping in this release and what is not, because the thesis is complete but the implementation is staged.

**v0.1 has the shape.** Four node types, markdown on disk, SQLite with FTS5 indexing, MCP stdio server, watchdog reconciliation, typed retrieval with the per-type policies described above. Constraints are guaranteed-surface. The pathways edges table exists and increments on every episode write. The frame is right. What v0.1 does *not* have is embeddings — retrieval is lexical (FTS5 BM25 plus type-aware re-ranking), not semantic. If you want vector-based similarity search today, v0.1 is not that.

**v0.2 adds the dynamics.** Embedding-based semantic recall alongside the lexical index — a local-first hybrid, similar in spirit to what Basic Memory already does with FastEmbed. Pattern promotion from repeated episodes, using the pathways edge weights. Decay on episodes so old events fall out of recall naturally. A scheduled `consolidate` pass that runs pattern promotion and decay together. That is the release that turns the static typing into a self-organizing system.

**v0.3 makes it visible.** An Obsidian plugin so the vault is a first-class notebook. A graph view of the activation network — nodes, edges, weights — so you can see the pathways layer instead of just trusting that it exists. Bidirectional editing so what you write by hand is memory the agent can use, and what the agent remembers is something you can read, edit, or throw away.

Implementation detail lives in `docs/architecture.md`. Ship order lives in the README roadmap. No dates.

## The big idea

Most agent-memory tools treat memory as a bucket of strings — either flat vector embeddings or proprietary JSON you cannot inspect. Savant cognition points at a different model: memory as a typed, interconnected, self-organizing system, where the shape of the node determines how it is treated and the connections between nodes emerge from how they get used. `all41n14lla` is the smallest shippable version of that intuition — typed markdown files on your disk, a lightweight pathways graph in SQLite, exposed over MCP. Every agent you use speaks the same protocol. Your memory is yours.

## Further reading

The five sources that directly shaped the design choices above. Claims in the body are tagged to whichever of these grounds them.

- **[Mem0](https://github.com/mem0ai/mem0)** — universal memory layer for AI agents; pluggable vector DB backend, Apache-2.0 licensed. Grounds the typed-by-scope observation (user/session/agent) and is named in `docs/comparison.md` as the closest hosted-memory competitor.
- **[Letta](https://github.com/letta-ai/letta)** — stateful agents with the MemGPT lineage; introduces "memory blocks" as typed, first-class slots for different kinds of agent context. Grounds the typed-memory finding.
- **[memory-graph](https://github.com/memory-graph/memory-graph)** — MCP memory server backed by a graph database. Grounds the graph-backed-memory finding and sets the reference point against which `all41n14lla` chose a lighter substrate (SQLite plus markdown) over a full graph DB.
- **[REMem: Reasoning with Episodic Memory in Language Agents](https://arxiv.org/abs/2602.13530)** — the academic backbone for treating episodic memory as a reasoning primitive rather than a storage trick. Grounds the "separate the reasoning engine from the memory system" argument.
- **[Sparse Distributed Representations](https://seanpedersen.github.io/posts/sparse-distributed-representations)** — Sean Pedersen's walkthrough of the Hawkins/Numenta pattern-overlap intuition. Grounds the pattern-indexed-retrieval finding and the design direction for the pathways graph and the v0.2 consolidate pass.

A head-to-head feature table against Basic Memory, MemPalace, Mem0, and the MCP reference memory server lives in `docs/comparison.md`. The five-problem diagnosis of why agent memory is broken in the first place lives in `docs/why.md`. The origin of the name lives in `ORIGIN.md`.
