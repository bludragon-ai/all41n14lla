# Design candidate: relevance-verifying recall (from jcode study, 2026-07-11)

**Source:** jcode's ambient memory (github.com/1jehuang/jcode; distilled at vault wiki/sources/jcode-harness.md).

**The idea worth stealing:** before injecting recall hits into context, an optional cheap "memory sideagent" verifies each hit is actually relevant to the live turn — and may do one more retrieval hop if the hits imply a better query. Kills the classic RAG failure (top-k cosine hits that are on-topic-adjacent but useless) without burning main-model tokens.

**a41 mapping:**
- Today: `recall` returns BM25/semantic top-k raw; the caller judges relevance.
- Candidate: `recall --verified` (or a `verify: true` param): pipe hits through a small local model (ollama llama3.2:3b — free, already on m1/i5) with the query + one-line judgment per hit (keep/drop/refine-query). Opt-in, so the fast path stays fast.
- Second jcode idea, cheaper: ambient extraction triggers (semantic drift / K turns / session end) — a41's predator loop already does session-end; drift-trigger is the novel bit.

**Next step (not now):** prototype `verify` as a post-filter in the recall path; bench precision on 20 real queries vs raw top-k. Zero API cost via ollama.

---

## VERDICT (2026-07-12): benched, **not shipping**. Do not re-litigate without new evidence.

Prototyped (`engine/verify.py` + `recall(verify=True)`, opt-in, 78 tests green) and benched on
the LIVE vault — 20 real queries, 210 hits, llama3.2:3b judge (`benchmarks/verified_recall.py`,
report in `benchmarks/verified_recall_report.json`). It fails on both horns:

| judge prompt | hits dropped | best hit survives? | latency |
|---|---|---|---|
| v1 strict RELEVANT/IRRELEVANT | **54%** | **NO** — killed the single best memory on 4/5 probes | +18.8 s/query |
| v2 recall-biased (drop only if clearly unrelated) | 10% | yes, 5/5 | +19.6 s/query |

- **v1 destroys recall.** `"email addresses jordan uses"` dropped the *Professional URLs and email
  identities* note; `"where do secrets live"` dropped *"Never commit secrets to git"*; `"missed call
  text back"` dropped the core salon front-desk product. A filter that deletes the answer is worse
  than no filter.
- **v2 is safe but inert** — 10% dropped, all noise-adjacent, nothing a caller would have been
  misled by. It buys ~nothing.
- **Either way it costs ~19 s** against a 47 ms raw query (~400×). Thread-pooling did NOT help:
  ollama serializes on one model slot (`OLLAMA_NUM_PARALLEL=1`), so N hits = N sequential
  generations. Latency is structural, not a tuning knob.
- The failure contract also degraded silently on 3/20 queries (ollama timeout → unfiltered hits,
  `verified: false`) — the caller has no way to notice.

**Why it doesn't transfer from jcode:** jcode's sideagent guards a *large, noisy, embedding-only*
top-k. a41 retrieves over 275 curated nodes with a deterministic constraint floor + typed BM25
rescoring — precision is already the strong suit. There is no RAG failure here to fix.

**What would have to change to revisit:** the vault an order of magnitude larger AND a judge that is
either batched (all hits in ONE generation) or non-generative (a cross-encoder / reranker). A
per-hit generative call is the wrong shape at any vault size.

The code stays on branch `verified-recall` as the experiment record — it is NOT merged to main and
`verify` defaults to False. The branch's genuinely good change is separable: `a3e4c4c` (FTS5 OR
semantics — multi-word recall queries no longer silently return `[]`).
