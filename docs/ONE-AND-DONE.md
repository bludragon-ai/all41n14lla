# One and Done — the self-compounding memory design

> Founder's directive (2026-07-10): "Make it as powerful as can be so I don't have to upgrade it —
> it just works and self-improves the more it's used. And make it so convenient that when people
> use it, they realize how powerful it is."
>
> Design answer in one line: **software degrades with use; memory should compound with use.**
> Everything below is a mechanism that makes the vault measurably better every week it runs,
> with zero knobs, zero babysitting, zero cloud.

---

## Part I — Power that compounds (the self-improving core)

### 1. Use-strengthened recall (Hebbian ranking)
Every recall that gets *used* (the node is cited again, re-remembered, or linked in the same session)
strengthens that node's salience; surfaced-but-ignored results decay slowly. "Neurons that fire
together wire together" as a ranking signal. After a month, recall isn't generic search — it's ranked
by what its owner actually finds useful. Implementation: a per-node usage ledger in SQLite feeding a
bounded salience multiplier. No API change, no user action, fully rebuildable.

### 2. Pathway learning (the associative signature)
Nodes recalled together form edges; repetition strengthens them (pathways exist in the codebase —
this makes them *learned*, not just declared). Over months the graph takes the shape of its owner's
mind — which is also the moat: a competitor can copy features, but not a year of someone's
co-recall patterns. Cold-start-proof differentiation.

### 3. Automatic sleep (consolidation as a rhythm, not a command)
`consolidate` becomes a background cadence (opt-out, not opt-in): episodic entries distill into
semantic lessons, duplicates merge, stale facts archive with supersession links. The vault gets
*cleaner* with age instead of rotting — the #1 failure mode of every memory system.

### 4. The two hemispheres audit each other (from TWO-BRAINS.md)
Literal + associative recall fused, with disagreement surfaced as drift candidates. Sleep resolves
the safe ones automatically (newer dated fact supersedes; the old one archives, never deletes) and
queues only true ambiguities. Self-cleaning memory that notices when it disagrees with itself.

### 5. Self-tuning fusion (bounded, invisible)
Fusion weights between hemispheres adapt slowly per memory-type from usage evidence (tiny learning
rate, hard bounds, deterministic constraint floor untouchable). The system tunes to its owner's
query style. No settings page exists because none is needed.

### 6. Self-measurement (prove the compounding)
During sleep, the system generates known-answer probes from the owner's own vault and scores its
recall against them. `inspect` reports the trend: "recall quality: 94%, up from 89% last month."
The product can *prove* it's getting better — which is also the marketing loop.

### 7. The structural guarantee (why upgrades can't hurt you)
Files are sacred; indexes are cattle. Every index (FTS, embeddings, salience, pathways) is
rebuildable from the markdown at any time. Version upgrades = reindex, never migrate. A failed
upgrade can cost at most a rebuild — never a memory. This is the engineering meaning of
"one and done": the part that persists is the part that can't break.

**Graceful degradation ladder:** no Ollama → left-brain only (v0.1 behavior) · no watchdog → lazy
reindex on next use · index corruption → auto-rebuild from files · nothing has a failure mode that
loses data, because data is markdown.

---

## Part II — Convenience that reveals the power

### 1. One command, every client
`uvx all41n14lla init` — detects installed MCP clients (Claude Desktop, Claude Code, Cursor,
Windsurf configs live at known paths), shows what it found, wires them all on one confirm.
Nobody hand-edits four JSON files. This single command is most of the adoption funnel.

### 2. Warm start (kill the cold-start, deliver day-one wow)
`all41n14lla adopt <folder>` — point it at an existing notes/Obsidian folder or a pasted chat
export → instant brain with something real to recall on day one. The empty-vault silence is why
memory tools churn; adoption should start with recall that already works.

### 3. The visceral demo (cross-agent continuity)
The one demo nobody else can run: *tell Claude something today — ask Cursor about it tomorrow.*
Same memory, different AI brands. That's the README gif, the pitch's proof, and Ana's episode.
("Swap the model, keep the mind" made visible.)

### 4. See your brain grow
`all41n14lla inspect --web` — a local one-page view: the graph, recent memories, salience heat,
the recall-quality trend line. Making the invisible visible is retention — and screenshot-able
brain graphs are organic marketing.

### 5. Progressive disclosure, no cliffs
Layer 0: agents use it silently over MCP (most users never type a command). Layer 1: the CLI for
the curious. Layer 2: the files themselves for the nerds. Each layer is complete; none is required.

### 6. Trust as a feature
Export is `cp -r` (it's your folder). A pause file stops all writes instantly. The privacy story
is the front page, not the appendix. Convenience includes the confidence to adopt.

---

## Roadmap (each version ships whole — no half-features)

| Version | Theme | Contents |
|---|---|---|
| **v0.2** | The power core | Two hemispheres + fusion recall + drift surfacing (TWO-BRAINS.md) |
| **v0.3** | The compounding | Hebbian salience · learned pathways · auto-sleep · self-benchmark |
| **v0.4** | The convenience | `init` client auto-wiring · `adopt` warm-start · `inspect --web` |
| **v1.0** | The promise | Stability contract (files-first, no-migration guarantee) · degradation ladder documented · the cross-agent demo as the front door |

**The promise, in product words:** *"Install it once. It gets smarter about you every day —
and it's still just markdown."*
