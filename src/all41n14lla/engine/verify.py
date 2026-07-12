"""Opt-in recall post-filter: judge each hit's relevance with a local model.

jcode-inspired "verified recall" (design/CANDIDATE-memory-sideagent.md): after
normal top-k retrieval, each hit is shown to a small local ollama model with
the query and a strict RELEVANT/IRRELEVANT judgment prompt. IRRELEVANT hits
are dropped. Strictly opt-in — the fast path never touches this module.

Failure contract: verification must NEVER break recall. Any transport error,
timeout, or malformed response aborts the filter and the caller returns the
unfiltered hits flagged ``verified: false``.
"""
from __future__ import annotations

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
TIMEOUT_S = 5.0

_PROMPT = (
    "You judge search results. Query: {query!r}\n"
    "Result:\n{content}\n\n"
    "Is this result relevant to the query? "
    "Answer with exactly one word: RELEVANT or IRRELEVANT."
)


def _judge(client: httpx.Client, query: str, content: str) -> bool:
    """True = keep. Unparseable answers keep the hit (drop only on a clear no)."""
    resp = client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": _PROMPT.format(query=query, content=content[:2000]),
            "stream": False,
            "options": {"temperature": 0, "num_predict": 4},
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    answer = resp.json().get("response", "").strip().upper()
    return not answer.startswith("IRRELEVANT")


def verify_hits(query: str, hits: list[dict]) -> tuple[list[dict], bool]:
    """Filter recall hit dicts through the local judge.

    Returns ``(hits, verified)``. Floor constraints (``floor: true``) are a
    deterministic guarantee and are never judged or dropped. On any ollama
    failure the ORIGINAL list is returned with ``verified=False`` — graceful
    degradation, never an exception.
    """
    if not hits:
        return hits, True
    try:
        with httpx.Client() as client:
            kept = [
                h
                for h in hits
                if h.get("floor") or _judge(client, query, h["content"])
            ]
        return kept, True
    except Exception:  # ponytail: any failure degrades to unfiltered — by contract
        return hits, False
