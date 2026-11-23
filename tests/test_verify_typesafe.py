"""Tests for the TypeSafe (Jev Noul) backend of verified recall.

All HTTP is mocked with ``httpx.MockTransport`` — no test here reaches the
network or spends a token. The contract: backend selection by env, keep/drop
by Noul probability vs threshold, one batched request per query, and every
failure (no key, timeout, malformed body, 401, 429) degrades to the unfiltered
hits flagged ``verified: false`` without the key leaking anywhere.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from all41n14lla.engine import verify as verify_mod
from all41n14lla.engine.storage import NODE_FOLDERS, Storage, default_db_path

SECRET = "ts-SECRET-key-do-not-leak-1234"


def _hits(*contents: str, floor_first: bool = False) -> list[dict]:
    hits = [
        {"id": f"id{i}", "content": c, "floor": False, "score": 1.0}
        for i, c in enumerate(contents)
    ]
    if floor_first:
        hits.insert(0, {"id": "floor", "content": "Never commit secrets.", "floor": True})
    return hits


class _Recorder:
    """A MockTransport handler that records requests and answers per a rule."""

    def __init__(self, respond):
        self.respond = respond
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)


def _noul_answers(prob_for_content):
    """Respond with a valid Noul answer for every question in the request."""

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        answers = {
            qid: {"type": "noul", "noul": prob_for_content(q["instructions"]["memory"])}
            for qid, q in body["questions"].items()
        }
        return httpx.Response(
            200,
            json={"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}},
        )

    return respond


@pytest.fixture
def typesafe_env(monkeypatch):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_BACKEND", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", SECRET)
    monkeypatch.delenv("ALL41N14LLA_VERIFY_THRESHOLD", raising=False)
    monkeypatch.delenv("ALL41N14LLA_TYPESAFE_MODEL", raising=False)


def _install(monkeypatch, handler) -> None:
    """Route every httpx.Client the verifier opens through a mock transport."""
    real_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(verify_mod.httpx, "Client", fake_client)


def _assert_no_leak(result, caplog) -> None:
    assert SECRET not in (result.reason or "")
    assert SECRET not in repr(result)
    assert SECRET not in caplog.text


# --- backend selection ------------------------------------------------------


def test_default_backend_is_ollama(monkeypatch):
    monkeypatch.delenv("ALL41N14LLA_VERIFY_BACKEND", raising=False)
    assert verify_mod.backend_name() == "ollama"


def test_unknown_backend_falls_back_to_ollama(monkeypatch):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_BACKEND", "gpt-9")
    assert verify_mod.backend_name() == "ollama"


def test_typesafe_backend_selected_and_ollama_untouched(typesafe_env, monkeypatch):
    monkeypatch.setattr(
        verify_mod, "_judge", lambda *a, **k: pytest.fail("ollama judge must not run")
    )
    rec = _Recorder(_noul_answers(lambda c: 0.9))
    _install(monkeypatch, rec)
    result = verify_mod.verify("python packaging", _hits("a", "b"))
    assert result.backend == "typesafe"
    assert result.verified is True
    assert rec.requests[0].url == httpx.URL(verify_mod.TYPESAFE_URL)


def test_ollama_backend_selected_by_env(monkeypatch):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_BACKEND", "ollama")
    monkeypatch.setattr(verify_mod, "_judge", lambda client, q, c: "keep" in c)
    result = verify_mod.verify("q", _hits("keep me", "drop me"))
    assert result.backend == "ollama"
    assert [h["content"] for h in result.hits] == ["keep me"]


# --- keep / drop by probability ----------------------------------------------


def test_keep_drop_by_default_threshold(typesafe_env, monkeypatch):
    probs = {"relevant": 0.93, "edge": 0.5, "noise": 0.07, "unsure": 0.49}
    _install(monkeypatch, _Recorder(_noul_answers(lambda c: probs[c])))
    result = verify_mod.verify("q", _hits(*probs))
    kept = {h["content"]: h["relevance"] for h in result.hits}
    assert kept == {"relevant": 0.93, "edge": 0.5}  # p >= 0.5 kept
    assert result.verified is True


def test_threshold_is_configurable(typesafe_env, monkeypatch):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_THRESHOLD", "0.9")
    probs = {"relevant": 0.93, "edge": 0.5}
    _install(monkeypatch, _Recorder(_noul_answers(lambda c: probs[c])))
    result = verify_mod.verify("q", _hits(*probs))
    assert [h["content"] for h in result.hits] == ["relevant"]


def test_invalid_threshold_degrades_unfiltered(typesafe_env, monkeypatch, caplog):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_THRESHOLD", "1.5")
    rec = _Recorder(_noul_answers(lambda c: 0.0))
    _install(monkeypatch, rec)
    hits = _hits("a", "b")
    result = verify_mod.verify("q", hits)
    assert result.hits == hits and result.verified is False
    assert "THRESHOLD" in result.reason
    assert rec.requests == []
    _assert_no_leak(result, caplog)


def test_floor_never_sent_or_dropped(typesafe_env, monkeypatch):
    rec = _Recorder(_noul_answers(lambda c: 0.0))  # judge drops everything
    _install(monkeypatch, rec)
    result = verify_mod.verify("secrets", _hits("noise", floor_first=True))
    assert [h["id"] for h in result.hits] == ["floor"]
    assert "relevance" not in result.hits[0]
    sent = json.loads(rec.requests[0].content)["questions"]
    assert all("Never commit" not in q["instructions"]["memory"] for q in sent.values())


def test_only_floor_hits_never_call_the_api(typesafe_env, monkeypatch):
    _install(monkeypatch, lambda r: pytest.fail("no request expected"))
    monkeypatch.setattr(verify_mod, "_typesafe_key", lambda: pytest.fail("no key lookup"))
    hits = [{"id": "f", "content": "x", "floor": True}]
    result = verify_mod.verify("q", hits)
    assert result.hits == hits and result.verified is True


# --- request shape + batching ------------------------------------------------


def test_one_batched_request_with_documented_shape(typesafe_env, monkeypatch):
    rec = _Recorder(_noul_answers(lambda c: 0.8))
    _install(monkeypatch, rec)
    verify_mod.verify("python packaging", _hits(*(f"memory {i}" for i in range(10))))
    assert len(rec.requests) == 1
    req = rec.requests[0]
    assert req.method == "POST"
    assert req.headers["authorization"] == f"Bearer {SECRET}"
    body = json.loads(req.content)
    assert body["model"] == "jev-latest"
    assert body["state"] == {"search_query": "python packaging"}
    assert len(body["questions"]) == 10
    q = body["questions"]["hit_0"]
    assert q["type"] == "noul"
    assert q["instructions"]["memory"] == "memory 0"
    assert "`memory`" in q["instructions"]["question"]
    assert set(q["criteria"]) == {"true", "false"}


def test_model_can_be_pinned(typesafe_env, monkeypatch):
    monkeypatch.setenv("ALL41N14LLA_TYPESAFE_MODEL", "jev-1.13.0")
    rec = _Recorder(_noul_answers(lambda c: 0.8))
    _install(monkeypatch, rec)
    verify_mod.verify("q", _hits("a"))
    assert json.loads(rec.requests[0].content)["model"] == "jev-1.13.0"


def test_content_truncated_per_hit(typesafe_env, monkeypatch):
    rec = _Recorder(_noul_answers(lambda c: 0.8))
    _install(monkeypatch, rec)
    verify_mod.verify("q", _hits("x" * 10_000))
    memory = json.loads(rec.requests[0].content)["questions"]["hit_0"]["instructions"]["memory"]
    assert len(memory) == verify_mod.CONTENT_CHARS


def test_splits_only_when_token_budget_requires(typesafe_env, monkeypatch):
    monkeypatch.setattr(verify_mod, "REQUEST_TOKEN_BUDGET", 1_200)
    rec = _Recorder(_noul_answers(lambda c: 0.8))
    _install(monkeypatch, rec)
    result = verify_mod.verify("q", _hits(*("y" * 2000 for _ in range(5))))
    # ~600 tokens per hit, ~80 fixed → 1 hit per request under a 1.2k budget
    assert len(rec.requests) == 5
    assert len(result.hits) == 5 and result.verified is True
    ids = [qid for r in rec.requests for qid in json.loads(r.content)["questions"]]
    assert ids == [f"hit_{i}" for i in range(5)]


# --- failure contract ----------------------------------------------------------


def _assert_unfiltered(result, hits, needle, caplog):
    assert result.hits == hits
    assert result.verified is False
    assert needle in result.reason
    assert "\n" not in result.reason
    _assert_no_leak(result, caplog)


def test_missing_key_degrades_unfiltered(monkeypatch, caplog):
    monkeypatch.setenv("ALL41N14LLA_VERIFY_BACKEND", "typesafe")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(verify_mod.sys, "platform", "linux")  # no keychain fallback
    _install(monkeypatch, lambda r: pytest.fail("no request without a key"))
    hits = _hits("a")
    _assert_unfiltered(verify_mod.verify("q", hits), hits, "no TYPESAFE_API_KEY", caplog)


def test_keychain_fallback_on_macos(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(verify_mod.sys, "platform", "darwin")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return verify_mod.subprocess.CompletedProcess(cmd, 0, stdout=SECRET + "\n", stderr="")

    monkeypatch.setattr(verify_mod.subprocess, "run", fake_run)
    assert verify_mod._typesafe_key() == SECRET
    assert calls == [["security", "find-generic-password", "-s", "TYPESAFE_API_KEY", "-w"]]


def test_keychain_miss_is_no_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(verify_mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        verify_mod.subprocess,
        "run",
        lambda cmd, **k: verify_mod.subprocess.CompletedProcess(cmd, 44, stdout="", stderr="not found"),
    )
    assert verify_mod._typesafe_key() is None


def test_timeout_degrades_unfiltered(typesafe_env, monkeypatch, caplog):
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    _install(monkeypatch, slow)
    hits = _hits("a", "b")
    _assert_unfiltered(verify_mod.verify("q", hits), hits, "timed out", caplog)


def test_connect_error_degrades_unfiltered(typesafe_env, monkeypatch, caplog):
    def down(request):
        raise httpx.ConnectError(f"refused {SECRET}", request=request)

    _install(monkeypatch, down)
    hits = _hits("a")
    _assert_unfiltered(verify_mod.verify("q", hits), hits, "unreachable", caplog)


@pytest.mark.parametrize("status", [401, 422, 429, 500, 529])
def test_http_errors_degrade_unfiltered(typesafe_env, monkeypatch, caplog, status):
    rec = _Recorder(
        lambda r: httpx.Response(status, json={"error": f"bad key {SECRET}"})
    )
    _install(monkeypatch, rec)
    hits = _hits("a", "b")
    result = verify_mod.verify("q", hits)
    _assert_unfiltered(result, hits, f"HTTP {status}", caplog)
    assert len(rec.requests) == 1  # no retries: recall stays fast


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        {"answers": {}},
        {"nope": 1},
        {"answers": {"hit_0": {"type": "noul"}, "hit_1": {"type": "noul", "noul": 0.5}}},
        {"answers": {"hit_0": {"noul": "0.9"}, "hit_1": {"noul": 0.5}}},
        {"answers": {"hit_0": {"noul": 1.7}, "hit_1": {"noul": 0.5}}},
        {"answers": {"hit_0": {"noul": True}, "hit_1": {"noul": 0.5}}},
        {"answers": [0.9, 0.1]},
    ],
)
def test_malformed_response_degrades_unfiltered(typesafe_env, monkeypatch, caplog, body):
    def respond(request):
        if isinstance(body, str):
            return httpx.Response(200, content=body.encode())
        return httpx.Response(200, json=body)

    _install(monkeypatch, respond)
    hits = _hits("a", "b")
    _assert_unfiltered(verify_mod.verify("q", hits), hits, "malformed", caplog)


def test_key_never_logged_on_success(typesafe_env, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _install(monkeypatch, _Recorder(_noul_answers(lambda c: 0.9)))
    result = verify_mod.verify("q", _hits("a"))
    _assert_no_leak(result, caplog)


# --- through the MCP recall tool -------------------------------------------------


@pytest.fixture
def scratch_vault(tmp_path: Path, monkeypatch) -> Path:
    vault = tmp_path / "vault"
    for folder in NODE_FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    with Storage(default_db_path(vault)):
        pass
    monkeypatch.setenv("ALL41N14LLA_VAULT", str(vault))
    return vault


def test_recall_tool_returns_relevance_metadata(scratch_vault, typesafe_env, monkeypatch):
    from all41n14lla.server import recall, remember

    remember(type="concept", content="Python packaging uses pyproject.toml.")
    remember(type="concept", content="Python snakes live in packaging crates at the zoo.")
    _install(
        monkeypatch,
        _Recorder(_noul_answers(lambda c: 0.04 if "zoo" in c else 0.91)),
    )
    hits = recall(query="python packaging", verify=True)
    assert len(hits) == 1
    assert hits[0]["relevance"] == 0.91
    assert hits[0]["verified"] is True
    assert "verify_reason" not in hits[0]


def test_recall_tool_failure_carries_reason(scratch_vault, typesafe_env, monkeypatch):
    from all41n14lla.server import recall, remember

    remember(type="concept", content="First fact about widgets.")
    remember(type="concept", content="Second fact about widgets.")
    _install(monkeypatch, lambda r: httpx.Response(429))
    hits = recall(query="widgets", verify=True)
    assert len(hits) == 2
    assert all(h["verified"] is False for h in hits)
    assert all(h["verify_reason"] == "typesafe returned HTTP 429" for h in hits)
    assert all(SECRET not in json.dumps(h) for h in hits)


def test_recall_without_verify_never_touches_typesafe(scratch_vault, typesafe_env, monkeypatch):
    from all41n14lla.server import recall, remember

    monkeypatch.setattr(verify_mod.httpx, "Client", lambda *a, **k: pytest.fail("no client"))
    monkeypatch.setattr(verify_mod, "_typesafe_key", lambda: pytest.fail("no key lookup"))
    remember(type="concept", content="Portable memory lives on disk.")
    hits = recall(query="portable")
    assert len(hits) == 1
    assert "verified" not in hits[0] and "relevance" not in hits[0]
