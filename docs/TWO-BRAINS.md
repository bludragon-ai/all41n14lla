# The Two-Brain Architecture (v0.2 direction)

> Origin: the founder's design instinct, 2026-07-10 — "two brains acting independently but mirroring
> the same things. We have a left and a right, and so should you."

## The idea, precisely

One life, two representations — independently queryable, always mirroring, reconciled at recall:

| | **Left hemisphere** (exists, v0.1) | **Right hemisphere** (v0.2) |
|---|---|---|
| Nature | The literal ledger | The associative field |
| Substrate | Markdown files + SQLite FTS5, typed retrieval, deterministic constraint floor | Local embedding index over the *same* files (e.g. Ollama `nomic-embed-text` — offline, $0) |
| Answers | "What exactly happened? What did we decide?" | "What does this remind me of? What belongs together?" |
| Failure mode | Misses paraphrase (keyword ≠ phrase) | Hallucinates similarity, fuzzy on facts |
| Trust model | Exact — quotable, greppable, git-diffable | Suggestive — never authoritative alone |

**Mirroring:** both hemispheres index the same markdown files. The existing watchdog reconciliation
extends to keep the embedding index in lockstep with FTS — one file changed on disk, two brains
updated, always. The files stay the single source of truth; both indexes are disposable and
rebuildable from them (nothing sacred lives in an index).

**The corpus callosum — `recall()` v2:**
1. Query hits both hemispheres in parallel.
2. Results fuse (reciprocal-rank fusion), with the deterministic constraint floor preserved —
   exact-match obligations can never be displaced by vibes.
3. **Disagreement is signal, not noise:** a strong keyword hit with zero semantic neighbors — or a
   tight semantic cluster the literal index can't corroborate — gets flagged as a *drift candidate*
   (stale fact, contradiction, or emerging theme) and queued for consolidation review. The hemispheres
   audit each other. This is the feature nobody else has: memory that notices when it disagrees
   with itself.

**Sleep:** consolidation (`consolidate`) is the hippocampal replay step — episodic entries distill
into semantic lessons while both indexes rebuild. (In humans this happens at night. Same here.)

## Honesty footnote (for the précis-minded)

Real human hemispheres are specialized-and-connected, not mirrored copies — the pop left/right split
is folklore. The neuroscience this actually rhymes with is **dual-coding** (verbatim + gist
representations) and **hippocampus→neocortex consolidation**. The left/right framing stays because
it communicates the design in one sentence — and the engineering it describes is real regardless.

## v0.2 build outline (fresh-session work, not tonight)

1. `hemisphere_r/` — embedding index module: local model via Ollama, per-node vectors stored in
   SQLite (same DB, new table), rebuildable from files.
2. Watcher extension — file event → FTS update (exists) + embedding upsert (new), one transaction.
3. `recall()` fusion — parallel query, RRF merge, constraint floor unchanged, `source` annotation
   per result (`literal` / `associative` / `both`).
4. Disagreement detector — threshold rules → `drift_candidates` table → surfaced via `inspect`
   and consolidation runs.
5. Benchmarks — extend `benchmarks/constraint_recall.py` with paraphrase-recall cases the left
   brain provably fails today, so the right brain's value is measured, not asserted.
6. Zero new services, zero cloud calls, offline-first preserved. If Ollama is absent, the package
   degrades gracefully to left-brain-only (exactly v0.1 behavior).
