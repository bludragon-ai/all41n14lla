"""Bench: does `recall(verify=True)` actually improve precision, or just cost latency?

The question design/CANDIDATE-memory-sideagent.md left open. Runs 20 real recall queries
against the LIVE vault, once raw and once verified, and prints every hit the local judge
dropped so a human can adjudicate whether the drop was right.

Run:  ALL41N14LLA_VAULT=~/all41n14lla/02-Brain/mcp-memory .venv/bin/python benchmarks/verified_recall.py
Needs ollama serving llama3.2:3b. Read-only — never writes to the vault.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from all41n14lla.engine.retrieval import retrieve          # noqa: E402
from all41n14lla.engine.storage import Storage, default_db_path  # noqa: E402
from all41n14lla.engine.verify import verify_hits          # noqa: E402
from all41n14lla.redact import redact                     # noqa: E402

# 20 queries a real caller actually asks this brain — not synthetic keyword probes.
QUERIES = [
    "how does Jordan want to be addressed",
    "salon front desk product pricing",
    "what is the outbound guardrail",
    "python package install policy",
    "which model for which task",
    "where do secrets live",
    "vault git remote policy",
    "missed call text back",
    "how does J like dashboards to look",
    "deletion policy before removing a file",
    "VPS migration to the i5",
    "job search resume positioning",
    "telegram vs imessage channel",
    "boil the ocean standard",
    "what should I do when a build spans many files",
    "stripe checkout",
    "ana avatar brand",
    "three strikes rule retry",
    "email addresses jordan uses",
    "notebooklm sweep",
]
LIMIT = 10


def main() -> int:
    _self_test_redact()  # PII scrub regression check — fail before any query
    vault = Path(os.environ["ALL41N14LLA_VAULT"]).expanduser()
    db = default_db_path(vault)
    report = []
    t_raw = t_ver = 0.0

    for q in QUERIES:
        t0 = time.perf_counter()
        with Storage(db) as s:
            outcome = retrieve(s, q, node_type=None, limit=LIMIT)
        hits = [
            {"id": n.id, "content": n.content, "floor": n.id in outcome.floor_ids}
            for n, _score in outcome.results
        ]
        t_raw += time.perf_counter() - t0

        t1 = time.perf_counter()
        kept, verified = verify_hits(q, hits)
        t_ver += time.perf_counter() - t1

        kept_ids = {h["id"] for h in kept}
        dropped = [h for h in hits if h["id"] not in kept_ids]
        # Report excerpts are LOCAL adjudication aids only — they are truncated
        # vault content and may carry PII (emails, phone numbers). They must
        # never be committed: benchmarks/verified_recall_report.json is in
        # .gitignore as the mechanical gate. Belt-and-suspenders: scrub the
        # highest-signal PII classes here too, so even a forced `git add -f`
        # cannot publish them.
        report.append({
            "query": q,
            "raw": len(hits),
            "kept": len(kept),
            "verified": verified,
            "dropped": [{"id": h["id"], "content": redact(h["content"])[:180]} for h in dropped],
        })
        print(f"{q!r:52} raw={len(hits):2} kept={len(kept):2} dropped={len(dropped):2} ok={verified}")

    raw_total = sum(r["raw"] for r in report)
    kept_total = sum(r["kept"] for r in report)
    print("\n" + "=" * 72)
    print(f"queries={len(QUERIES)}  raw hits={raw_total}  kept={kept_total}  "
          f"dropped={raw_total - kept_total} ({(raw_total - kept_total) / max(raw_total, 1):.0%})")
    print(f"latency: raw {t_raw / len(QUERIES) * 1000:.0f} ms/query  "
          f"verify +{t_ver / len(QUERIES) * 1000:.0f} ms/query")
    print(f"empty-result queries: raw {sum(1 for r in report if r['raw'] == 0)}  "
          f"verified {sum(1 for r in report if r['kept'] == 0)}")

    out = Path(__file__).parent / "verified_recall_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\ndrops written to {out} — adjudicate each: was it really irrelevant?")
    return 0


def _self_test_redact() -> None:
    """Regression check — the scrub must actually bite on every class."""
    sample = "call (415) 555-0132 or me@example.com, card 4111111111111111"
    out = redact(sample)
    assert "[phone]" in out and "[email]" in out and "[digits]" in out
    assert "me@example.com" not in out and "555-0132" not in out and "4111111111111111" not in out


if __name__ == "__main__":
    raise SystemExit(main())
