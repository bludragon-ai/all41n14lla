# Why all41n14lla

Agent memory is broken in five specific ways. This document explains what those are, what a correct solution looks like, and why the shape of `all41n14lla` follows from the diagnosis.

## The five problems

**1. Models forget mid-session.** Context windows are finite and the relevant bits are evicted before the task finishes. A model that helped you debug a migration an hour ago cannot tell you what it changed. "Just use a bigger context" is not an answer — the information density inside a context window drops as you fill it, and you pay linearly for tokens the model is using to remember things you could have stored on disk for free.

**2. Vendor-locked memory stores trap your data.** The current crop of hosted memory services keep your memories on their servers, indexed by their embeddings, exposed through their SDKs. Your data is portable only if you accept their export format, their rate limits, and their billing. The moment you want to switch tools, migrate models, or run offline, the portability story evaporates.

**3. Memory does not cross agents.** Notes you captured inside one assistant do not appear inside another. Each client rebuilds its own silo. The user, who is the only person with a stable identity across all of these tools, is the one thing that cannot carry state across them. This is backwards.

**4. Most memory is an opaque blob.** Vector stores with no human-readable layer mean you cannot see what the agent wrote down, cannot audit what it chose to remember about you, and cannot correct it. Memory you cannot read is memory you cannot trust.

**5. There is no offline-first option.** Memory that requires a round trip to someone else's cloud stops working on a plane, on a spotty connection, or inside a firewalled environment. For a feature as foundational as "remember what we just did," that is unacceptable.

## Memory does not belong inside the model

The dominant approach — jam more context into the prompt and hope the model sorts it out — conflates two different jobs. A language model is a knowledge engine and a reasoning engine. It is not a storage engine. Treating it as one inflates token costs, makes retrieval non-deterministic, and ties your recall quality to whichever attention heads happen to fire that turn.

The correct mental model is the one humans already use. You do not keep every note you have ever taken inside your own head. You keep it on paper, in a notebook, in a file system — somewhere durable, searchable, and indexed by something smarter than recency. You pull the relevant bits back into working memory when you need them. That boundary is what makes human long-term memory practical.

Agents should work the same way. Storage lives on the user's disk. Retrieval is a tool call. The model reasons over whatever the retrieval layer hands it. Memory stops being a mystery emergent property of the LLM and becomes an ordinary, debuggable piece of infrastructure.

## The portable contract: markdown plus MCP

Two formats already exist for the two halves of this problem.

Markdown is how humans write durable notes. Plain text, easy to diff, readable in any editor, searchable with `grep`, versionable with git, renderable in Obsidian, sync-friendly with Syncthing or Dropbox. Frontmatter gives you structured metadata — id, type, tags, timestamps — without sacrificing human readability. If an agent wrote it down, you can open the file and see exactly what it remembered.

The Model Context Protocol is how agents already connect to tools. Claude Code, Claude Desktop, Cursor, and a growing list of clients speak it natively. If you expose memory as an MCP server, every one of those clients gets `remember`, `recall`, `forget`, and `inspect` for free. No SDK lock-in, no per-client shim, no bespoke integration per tool.

The intersection is obvious. Store memory as markdown files on the user's disk. Index them locally with SQLite and FTS5. Expose the store over MCP stdio. The user owns the data in a format they already know how to back up. Any MCP-capable agent can read and write to it. Swap your agent tomorrow and your memory follows you.

That is `all41n14lla`.

## Why four node types

A memory system that treats every entry the same way is a memory system that retrieves the wrong thing at the wrong time. Different memories have different shapes, and the retrieval policy has to match.

- **Concepts** are stable ideas — the definitions and mental models you want the agent to keep straight. They update rarely and should be surfaced whenever their topic comes up.
- **Patterns** are repeated behaviors — things you do consistently enough that they deserve to be encoded as tendencies. They are derived, not stated, and get promoted from episodes once the repetition crosses a threshold.
- **Episodes** are specific events — what happened on Tuesday, what got decided in that meeting, what the error was. They are high volume and should decay, because most of them stop mattering once the situation they describe is over.
- **Constraints** are hard rules — "never commit with `--no-verify`", "always use pipx, not system pip". They should never decay, should surface early, and should be treated as non-negotiable inputs to the agent's reasoning.

One store, four retrieval policies. Episodes decay. Constraints do not. Patterns are promoted, not written. Concepts are linked. The shape of the node determines how it is treated. This is the thing most memory systems get wrong: they give you one bucket and one ranking function and wonder why the agent surfaces a three-month-old debugging session in response to a question about your coding style.

## Where this goes

**v0.1** ships the foundation: storage, the four node types, SQLite plus FTS5 indexing, and an MCP server that exposes `remember` / `recall` / `forget` / `inspect`. Lexical search, local, offline, portable.

**v0.2** adds the interesting retrieval work: embedding-based semantic recall, pattern promotion from repeated episodes, decay on episodes, and a `consolidate` pass that runs on a schedule.

**v0.3** opens it up to humans: an Obsidian plugin so the vault is a first-class notebook, a graph view for nodes and links, and bidirectional editing so what you write by hand is memory the agent can use, and what the agent remembers is something you can read, edit, or throw away.

Memory is infrastructure. It should live on your disk, speak a protocol everyone already supports, and be something you can open in a text editor. Nothing about that is novel. The novel part is shipping it.
