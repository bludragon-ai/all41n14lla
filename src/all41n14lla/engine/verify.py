"""Opt-in recall post-filter: judge each hit's relevance before returning it.

jcode-inspired "verified recall" (design/CANDIDATE-memory-sideagent.md): after
normal top-k retrieval, each non-floor hit is judged against the query and the
ones judged irrelevant are dropped. Strictly opt-in — the fast path never
touches this module.

Two backends, chosen by ``ALL41N14LLA_VERIFY_BACKEND``:

- ``ollama`` (default): a local ``llama3.2:3b`` answers RELEVANT/IRRELEVANT,
  one request per hit. Free, local, no key.
- ``typesafe``: TypeSafe's Jev answers one **Noul** per hit (the probability
  that the memory is relevant to the query), all hits for one query batched
  into a single ``POST /v1/systemone`` request. Hits with ``p >= threshold``
  are kept; each kept hit carries its probability as ``relevance``.
  Docs: https://docs.typesafe.ai/primitives/noul.md and
  https://docs.typesafe.ai/api.md

Failure contract (both backends): verification must NEVER break recall. Any
missing key, transport error, timeout, non-2xx status (401, 429, 529, ...),
or malformed response aborts the filter and the caller returns the unfiltered
hits flagged ``verified: false`` with a one-line ``reason``. No retries: a
recall must stay fast, and a 429 simply degrades to unfiltered.

Secrets: the TypeSafe key is read from ``TYPESAFE_API_KEY`` or, on macOS,
the login keychain (service ``TYPESAFE_API_KEY``). It is only ever placed in
the Authorization header — never logged, never put in a reason string, never
echoed from an exception (reasons are built from our own text, not ``str(exc)``).
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from dataclasses import dataclass

import httpx

# --- ollama backend -------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
TIMEOUT_S = 5.0

_PROMPT = (
    "You judge search results. Query: {query!r}\n"
    "Result:\n{content}\n\n"
    "Is this result relevant to the query? "
    "Answer with exactly one word: RELEVANT or IRRELEVANT."
)

# --- typesafe backend -----------------------------------------------------

TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = "jev-latest"
TYPESAFE_TIMEOUT_S = 8.0
# Noul docs: "Use 0.5 when yes and no are equally easy to act on." Dropping a
# relevant memory and keeping an irrelevant one cost about the same here (the
# caller is an agent that can ignore noise but can't see what was dropped), so
# 0.5 is the documented neutral point. Lower it to favour recall.
DEFAULT_THRESHOLD = 0.5
# Content cap per hit, matching the ollama backend.
CONTENT_CHARS = 2000
# Jev 1.13 context: 64k tokens per request (state + all questions). Pack hits
# into requests well under that, estimating ~4 chars per token.
REQUEST_TOKEN_BUDGET = 48_000
_KEYCHAIN_SERVICE = "TYPESAFE_API_KEY"

# The question is the same for every hit; only the memory changes. Structured
# instructions (question in one field, data in another) per the Noul docs'
# "Structured instructions" section.
_NOUL_QUESTION = (
    "Is `memory` relevant to the search query in `search_query`, i.e. would it "
    "help answer or inform that query?"
)
_NOUL_CRITERIA = {
    "true": "The memory is about the query's subject or directly informs it.",
    "false": "The memory is about something else; any word overlap is incidental.",
}


class VerifyError(Exception):
    """A verification failure with a safe, secret-free one-line reason."""


@dataclass
class VerifyResult:
    hits: list[dict]
    verified: bool
    reason: str | None = None
    backend: str = "ollama"


def _judge(client: httpx.Client, query: str, content: str) -> bool:
    """True = keep. Unparseable answers keep the hit (drop only on a clear no)."""
    resp = client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": _PROMPT.format(query=query, content=content[:CONTENT_CHARS]),
            "stream": False,
            "options": {"temperature": 0, "num_predict": 4},
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    answer = resp.json().get("response", "").strip().upper()
    return not answer.startswith("IRRELEVANT")


def _verify_ollama(query: str, hits: list[dict]) -> VerifyResult:
    try:
        with httpx.Client() as client:
            kept = [
                h
                for h in hits
                if h.get("floor") or _judge(client, query, h["content"])
            ]
        return VerifyResult(kept, True, backend="ollama")
    except Exception as exc:  # noqa: BLE001 — any failure degrades to unfiltered, by contract
        return VerifyResult(
            hits, False, f"ollama unavailable ({type(exc).__name__})", "ollama"
        )


# --- typesafe -------------------------------------------------------------


def _typesafe_key() -> str | None:
    """Env first, then the macOS login keychain. Never printed or logged."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:  # noqa: BLE001 — no keychain is the same as no key
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _threshold() -> float:
    raw = os.environ.get("ALL41N14LLA_VERIFY_THRESHOLD")
    if raw is None or raw.strip() == "":
        return DEFAULT_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        raise VerifyError("invalid ALL41N14LLA_VERIFY_THRESHOLD (want 0..1)") from None
    if not (0.0 <= value <= 1.0) or math.isnan(value):
        raise VerifyError("invalid ALL41N14LLA_VERIFY_THRESHOLD (want 0..1)")
    return value


def _noul_question(content: str) -> dict:
    return {
        "type": "noul",
        "instructions": {
            "memory": content[:CONTENT_CHARS],
            "question": _NOUL_QUESTION,
        },
        "criteria": dict(_NOUL_CRITERIA),
    }


def _batches(query: str, judged: list[tuple[int, dict]]) -> list[list[tuple[int, dict]]]:
    """Pack hits into as few requests as the per-request token budget allows."""
    fixed = (len(query) + len(_NOUL_QUESTION) + 200) // 4
    batches: list[list[tuple[int, dict]]] = []
    current: list[tuple[int, dict]] = []
    used = fixed
    for item in judged:
        cost = (min(len(item[1]["content"]), CONTENT_CHARS) + len(_NOUL_QUESTION) + 200) // 4
        if current and used + cost > REQUEST_TOKEN_BUDGET:
            batches.append(current)
            current, used = [], fixed
        current.append(item)
        used += cost
    if current:
        batches.append(current)
    return batches


def _ask_typesafe(
    client: httpx.Client, key: str, model: str, query: str, batch: list[tuple[int, dict]]
) -> dict[int, float]:
    """One request: one Noul per hit. Returns {hit index: p(relevant)}."""
    questions = {f"hit_{i}": _noul_question(h["content"]) for i, h in batch}
    try:
        resp = client.post(
            TYPESAFE_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"state": {"search_query": query}, "model": model, "questions": questions},
            timeout=TYPESAFE_TIMEOUT_S,
        )
    except httpx.TimeoutException:
        raise VerifyError("typesafe timed out") from None
    except httpx.HTTPError as exc:
        raise VerifyError(f"typesafe unreachable ({type(exc).__name__})") from None
    if resp.status_code != 200:
        raise VerifyError(f"typesafe returned HTTP {resp.status_code}")
    try:
        answers = resp.json()["answers"]
        probs: dict[int, float] = {}
        for i, _ in batch:
            ans = answers[f"hit_{i}"]
            p = ans["noul"]
            if isinstance(p, bool) or not isinstance(p, (int, float)):
                raise TypeError
            p = float(p)
            if not (0.0 <= p <= 1.0) or math.isnan(p):
                raise ValueError
            probs[i] = p
    except Exception:  # noqa: BLE001 — any shape problem is "malformed"
        raise VerifyError("typesafe response malformed") from None
    return probs


def _verify_typesafe(query: str, hits: list[dict]) -> VerifyResult:
    try:
        threshold = _threshold()
        judged = [(i, h) for i, h in enumerate(hits) if not h.get("floor")]
        if not judged:
            return VerifyResult(hits, True, backend="typesafe")
        key = _typesafe_key()
        if not key:
            raise VerifyError("no TYPESAFE_API_KEY in env or keychain")
        model = os.environ.get("ALL41N14LLA_TYPESAFE_MODEL", "").strip() or TYPESAFE_MODEL
        probs: dict[int, float] = {}
        with httpx.Client() as client:
            for batch in _batches(query, judged):
                probs.update(_ask_typesafe(client, key, model, query, batch))
    except VerifyError as exc:
        return VerifyResult(hits, False, str(exc), "typesafe")
    except Exception as exc:  # noqa: BLE001 — never break recall
        return VerifyResult(hits, False, f"typesafe failed ({type(exc).__name__})", "typesafe")

    kept: list[dict] = []
    for i, h in enumerate(hits):
        if h.get("floor"):
            kept.append(h)
        elif probs[i] >= threshold:
            kept.append({**h, "relevance": round(probs[i], 4)})
    return VerifyResult(kept, True, backend="typesafe")


# --- public ----------------------------------------------------------------

BACKENDS = ("ollama", "typesafe")


def backend_name() -> str:
    """The configured backend; unknown values fall back to the default."""
    name = os.environ.get("ALL41N14LLA_VERIFY_BACKEND", "").strip().lower()
    return name if name in BACKENDS else "ollama"


def verify(query: str, hits: list[dict]) -> VerifyResult:
    """Filter recall hit dicts through the configured judge.

    Floor constraints (``floor: true``) are a deterministic guarantee and are
    never judged or dropped. On any failure the ORIGINAL list is returned with
    ``verified=False`` and a one-line reason — graceful degradation, never an
    exception.
    """
    name = backend_name()
    if not hits:
        return VerifyResult(hits, True, backend=name)
    if name == "typesafe":
        return _verify_typesafe(query, hits)
    return _verify_ollama(query, hits)


def verify_hits(query: str, hits: list[dict]) -> tuple[list[dict], bool]:
    """Back-compat wrapper: ``(hits, verified)``."""
    result = verify(query, hits)
    return result.hits, result.verified
