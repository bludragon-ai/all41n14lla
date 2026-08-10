"""Constraint-recall benchmark: the deterministic floor vs pure BM25.

The question this measures: when a hard rule is buried under realistic
operational noise, does a recall for the *operational situation* surface the
rule in the top 5?

- **baseline** — `engine.search` (pure BM25 phrase match, the v0.1 behavior)
- **floor**    — `engine.retrieval.retrieve` (the deterministic constraint floor)

Method: 20 scenarios across common ops domains. Each scenario seeds a fresh
throwaway vault with ONE tagged constraint and 50 noise episodes that contain
the query phrasing verbatim (the way standups and logs actually talk), then
asks one operational question and checks whether the rule lands in the top 5.

In 4 of the 20 scenarios the rule's own text happens to contain the
operational phrase, giving BM25 a fair chance to catch it lexically — the
baseline number below is whatever was actually measured, not invented.

Honesty notes, stated up front:
- The floor's guarantee is tag-scoped: every scenario's rule is tagged, and
  every query shares at least one term with those tags. An untagged rule
  would NOT be rescued (see README "precondition").
- The baseline is hurt by two real v0.1 behaviors working together: phrase
  matching (the query must appear contiguously) and top-N truncation. The
  floor sidesteps both deterministically — that is the point.

Run it yourself:

    .venv/bin/python benchmarks/constraint_recall.py
"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path

from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.retrieval import retrieve
from all41n14lla.engine.search import search
from all41n14lla.engine.storage import Storage, default_db_path, folder_for

SEED = 41
TOP_K = 5
NOISE_PER_SCENARIO = 50

# (domain tags, rule text, operational query, noise verb-phrase)
# Scenarios marked phrase_in_rule=True embed the query phrasing in the rule
# itself so the BM25 baseline gets honest lexical chances.
SCENARIOS = [
    (["deploy", "release", "safety"], "never deploy to production on Fridays",
     "deploy the release", "deployed the release", False),
    (["secrets", "credentials"], "secrets never leave the keychain — no plaintext env files in repos",
     "rotate the credentials", "rotated the credentials", False),
    (["db", "migration"], "every schema change ships with a tested down-migration",
     "run the migration", "ran the migration", False),
    (["billing", "refunds"], "refunds above $100 require a second approver",
     "process the refund", "processed the refund", False),
    (["pii", "logging"], "request bodies containing PII are never written to logs",
     "check the logging", "checked the logging", False),
    (["oncall", "paging"], "page a human before silencing any production alert",
     "silence the paging alert", "silenced the paging alert", False),
    (["backup", "restore"], "test a restore before trusting any backup",
     "verify the backup", "verified the backup", False),
    (["auth", "tokens"], "access tokens expire in 15 minutes, no exceptions",
     "refresh the tokens", "refreshed the tokens", False),
    (["rate", "limits"], "public endpoints ship with rate limits from day one",
     "raise the rate limits", "raised the rate limits", False),
    (["vendor", "contracts"], "no vendor contract auto-renews without review",
     "renew the vendor contract", "renewed the vendor contract", False),
    (["branch", "merge"], "main is protected — merges require green CI",
     "merge the branch", "merged the branch", False),
    (["cache", "invalidation"], "cache TTLs are set explicitly, never default",
     "clear the cache", "cleared the cache", False),
    (["email", "sends"], "customer email sends are always a human click",
     "send the email batch", "sent the email batch", False),
    (["pricing", "discounts"], "discounts beyond 20 percent need founder sign-off",
     "apply the discount", "applied the discount", False),
    (["staging", "data"], "staging never holds real customer data",
     "seed the staging data", "seeded the staging data", False),
    (["dns", "cutover"], "DNS cutovers happen Tuesday mornings with rollback ready",
     "switch the dns", "switched the dns", False),
    # — phrase-in-rule scenarios: BM25 gets a fair lexical shot —
    (["deploy", "hotfix"], "before you deploy the hotfix, confirm the incident channel agrees",
     "deploy the hotfix", "deployed the hotfix", True),
    (["keys", "rotation"], "when you rotate the keys, update the escrow copy the same hour",
     "rotate the keys", "rotated the keys", True),
    (["invoice", "payment"], "before you send the invoice, verify the PO number matches",
     "send the invoice", "sent the invoice", True),
    (["incident", "postmortem"], "after you close the incident, the postmortem lands within 48 hours",
     "close the incident", "closed the incident", True),
]

NOISE_TEMPLATES = [
    "standup note {i}: {verb} for ticket {i}, all checks passed",
    "log {i}: {verb} on staging, then {verb} again after the fix",
    "weekly summary {i}: team {verb} twice, retro scheduled",
    "{verb} during the maintenance window, runbook step {i} complete",
    "pairing session {i}: {verb} while debugging the flaky suite",
]


def run() -> None:
    rng = random.Random(SEED)
    baseline_hits = 0
    floor_hits = 0
    rows = []

    for tags, rule, query, verb, phrase_in_rule in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            for nt in NodeType:
                (vault / folder_for(nt)).mkdir(parents=True)
            with Storage(default_db_path(vault)) as storage:
                rule_node = MemoryNode(
                    type=NodeType.CONSTRAINT, content=rule, tags=list(tags)
                )
                rule_node.write(
                    vault / folder_for(NodeType.CONSTRAINT) / f"{rule_node.id}.md"
                )
                storage.upsert_node(rule_node)
                for i in range(NOISE_PER_SCENARIO):
                    template = rng.choice(NOISE_TEMPLATES)
                    node = MemoryNode(
                        type=NodeType.EPISODE,
                        content=template.format(i=i, verb=verb),
                        tags=[tags[0], "standup"],
                    )
                    node.write(
                        vault / folder_for(NodeType.EPISODE) / f"{node.id}.md"
                    )
                    storage.upsert_node(node)

                base = search(storage, query, limit=TOP_K)
                base_hit = rule_node.id in [n.id for n, _ in base]
                flo = retrieve(storage, query, limit=TOP_K)
                floor_hit = rule_node.id in [n.id for n, _ in flo.results]

        baseline_hits += base_hit
        floor_hits += floor_hit
        rows.append((query, phrase_in_rule, base_hit, floor_hit))

    n = len(SCENARIOS)
    print(f"constraint recall@{TOP_K} under {NOISE_PER_SCENARIO}-episode noise — {n} scenarios (seed {SEED})")
    print(f"{'query':<28} {'phrase-in-rule':<15} {'BM25 top-5':<11} floor")
    for query, pir, b, f in rows:
        print(f"{query:<28} {pir!s:<15} {'HIT' if b else 'miss':<11} {'HIT' if f else 'miss'}")
    print("-" * 64)
    print(f"baseline (pure BM25):        {baseline_hits}/{n}  ({100 * baseline_hits / n:.0f}%)")
    print(f"deterministic floor:         {floor_hits}/{n}  ({100 * floor_hits / n:.0f}%)")


if __name__ == "__main__":
    run()
