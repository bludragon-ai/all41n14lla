# The Last Version — how a self-improving system escapes versioning

> Founder's question (2026-07-10): "How do we go beyond v2, v3 — and be the final one?
> Since it's supposed to be self-improving."
>
> Honest answer: split what "improves" into three layers. Each escapes versioning a different way.
> Two are already designed. The third needs the three moves below — and they're real, not slogans.

## The three layers of improvement

| Layer | What improves | How it escapes versions |
|---|---|---|
| **Content** (the vault) | The memories themselves | Already compounding (ONE-AND-DONE.md): Hebbian salience, learned pathways, auto-sleep. Improves forever without a single release. |
| **Behavior** (policies, weights, rules) | How the system ranks, consolidates, decides | **Move B:** behavior lives in *data*, not code — so it evolves without releases. |
| **Code** (the kernel) | Capabilities, fixes, protocol | **Moves A + C:** shrink it until it can be *finished*, then let its host agents service it. |

---

## Move A — A kernel small enough to finish (the TeX/SQLite move)

Software stays unfinished because it keeps absorbing features. The escape is subtraction: freeze a
tiny kernel behind a formal contract and declare it *complete* — the way TeX froze (its version
number converges on π) and SQLite pledged support to 2050 on a stable file format.

The all41n14lla kernel is already almost this small: **files + index + five MCP verbs**
(`remember` / `recall` / `forget` / `inspect` / `consolidate`). The frozen contract:

1. Memory is markdown + frontmatter on the owner's disk. Forever readable by humans and `grep`.
2. The protocol is MCP stdio. Five verbs, stable signatures.
3. Every index is rebuildable from the files. Upgrades reindex; they never migrate.
4. The constitution (below) is not self-modifiable.

Everything not in the kernel — importers, dashboards, exotic retrievers — lives *outside* it and can
churn freely without touching the finished core. **v1.0 is the last feature version of the kernel.
After that there are only birthdays.**

## Move B — Behavior lives in data (the constitutional move)

The system's operating rules — retrieval policies per memory type, consolidation cadence and rules,
fusion weights, decay rates — become **memory entries themselves**: readable markdown the engine
interprets at runtime. (This is the constitutional-memory pattern: Constitution → Contract →
Adaptation → Implementation.)

Then self-improvement of *behavior* needs no release:

- During sleep, the self-benchmark produces evidence ("paraphrase recall underperforms on type X").
- The system drafts a **policy adjustment as a memory entry** — human-readable, diffable, reversible.
- Bounded zones apply automatically (a weight inside its hard limits) — applied silently.
- Anything outside bounds waits for the owner's one tap. Every change is a file in git-able history;
  every change is revertible by deleting a file.

**The constitution — the part that may never self-modify:** never delete (archive with supersession
only) · files are the single truth · offline-first · the deterministic constraint floor · the bounds
themselves. Improvement is free *inside* the fence; the fence is not up for negotiation. A
self-improving system without a constitution is not a product, it's a liability.

## Move C — The mechanic lives in the car (the 2026 move)

Here is the fact no previous "final version" could use: **all41n14lla's users are coding agents.**
The host that calls `recall` can also read code, diagnose, and patch. So the kernel's maintenance
loop is designed for its own hosts:

1. Self-diagnosis: the sleep benchmark and watchdog write **improvement tickets** as structured,
   human-readable memory entries ("FTS rebuild slowed 3×; suspected cause; suggested fix; test to
   prove it").
2. The repo ships `MAINTENANCE.md` — a repair manual *written for AI agents*: invariants, test
   commands, the constitution, and exactly how to apply a ticket without breaking the contract.
3. The owner's own agent applies the fix **on the owner's tap**, runs the suite, and the vault
   remembers the repair as an episode.
4. Recurring tickets across installations become upstream issues by *choice* (an owner shares a
   ticket file; there is no telemetry — the project never phones home).

The upgrade mechanism isn't the author shipping releases. It's every installation carrying its own
mechanic, guided by the system's own self-diagnosis, fenced by the constitution, gated by its owner.

## The immortality floor (what "final" honestly guarantees)

No software escapes environmental drift — protocols evolve, OSes change. The honest promise is
stronger than "we'll keep shipping": even in total abandonment, **the memory is immortal** —
markdown outlives every company and every protocol — and the kernel is small enough that any
competent agent can rebuild or port it in an afternoon *from the files alone*, using the shipped
repair manual. The data cannot be held hostage by the code. That is the real meaning of the last
version: not software that never changes, but memory that no change can ever take from you.

---

**The product sentence:** *"v1 is the last version. It improves itself inside a constitution it
cannot touch, its own host agents service it on your say-so, and even if every line of code died
tomorrow — your memory is still just markdown on your disk."*
