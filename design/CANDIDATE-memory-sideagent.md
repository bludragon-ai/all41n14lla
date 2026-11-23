# Design candidate: relevance-verifying recall (from jcode study, 2026-07-11)

**Source:** jcode's ambient memory (github.com/1jehuang/jcode).

**The idea worth stealing:** before injecting recall hits into context, an optional cheap "memory sideagent" verifies each hit is actually relevant to the live turn — and may do one more retrieval hop if the hits imply a better query. Kills the classic RAG failure (top-k cosine hits that are on-topic-adjacent but useless) without burning main-model tokens.

**a41 mapping:**
- Today: `recall` returns BM25/semantic top-k raw; the caller judges relevance.
- Candidate: `recall --verified` (or a `verify: true` param): pipe hits through a small local model (ollama llama3.2:3b — free, runs on the local machine) with the query + one-line judgment per hit (keep/drop/refine-query). Opt-in, so the fast path stays fast.
- Second jcode idea, cheaper: ambient extraction triggers (semantic drift / K turns / session end) — drift-trigger is the novel bit.

**Next step (not now):** prototype `verify` as a post-filter in the recall path; bench precision on 20 real queries vs raw top-k. Zero API cost via ollama.

---

## VERDICT (2026-07-12): benched, **not shipping**. Do not re-litigate without new evidence.

Prototyped as `engine/verify.py` + `recall(verify=True)` (opt-in, off by default) and benched with `benchmarks/verified_recall.py` against a populated local vault: 20 queries, ~200 hits, llama3.2:3b judge. A strict RELEVANT/IRRELEVANT prompt dropped about half the hits, including the best answer on most probes. A recall-biased prompt dropped about 10%, all noise-adjacent. Either way it added ~19 s per query against ~47 ms raw, because ollama serializes generations on one model slot. Verdict: keep it opt-in. Revisit only with a batched or non-generative judge (cross-encoder/reranker) on a much larger vault.
