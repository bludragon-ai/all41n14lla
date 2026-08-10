# Graph Report - all41n14lla  (2026-07-19)

## Corpus Check
- 50 files · ~32,328 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 499 nodes · 868 edges · 37 communities (29 shown, 8 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 140 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `26b962e2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- MemoryNode
- wire_all
- cli.py
- VaultEventHandler
- Storage
- search
- CliRunner
- server.py
- default_db_path
- Part I — Power that compounds (the self-improving core)
- Changelog
- The 60-second run
- test_server.py
- test_verify.py
- Savant cognition as memory architecture
- FIXES — 2026-06-10 night shift
- Proposed, not done
- all41n14lla
- README.md
- Quickstart — Claude Desktop
- verify_hits
- Contributing
- Architecture
- The Last Version — how a self-improving system escapes versioning
- What is all41n14lla? (the say-it-out-loud card)
- The Two-Brain Architecture (v0.2 direction)
- Why all41n14lla
- Comparison
- pull_request_template.md
- Design candidate: relevance-verifying recall (from jcode study, 2026-07-11)
- __init__.py
- pathways.py
- __init__.py
- README.md
- conftest.py
- all41n14lla

## God Nodes (most connected - your core abstractions)
1. `MemoryNode` - 44 edges
2. `Storage` - 40 edges
3. `default_db_path()` - 34 edges
4. `retrieve()` - 26 edges
5. `wire_all()` - 21 edges
6. `VaultEventHandler` - 20 edges
7. `folder_for()` - 19 edges
8. `_write()` - 19 edges
9. `search()` - 16 edges
10. `NodeType` - 12 edges

## Surprising Connections (you probably didn't know these)
- `run()` --calls--> `MemoryNode`  [INFERRED]
  benchmarks/constraint_recall.py → src/all41n14lla/engine/nodes.py
- `run()` --calls--> `retrieve()`  [INFERRED]
  benchmarks/constraint_recall.py → src/all41n14lla/engine/retrieval.py
- `run()` --calls--> `search()`  [INFERRED]
  benchmarks/constraint_recall.py → src/all41n14lla/engine/search.py
- `main()` --calls--> `retrieve()`  [INFERRED]
  benchmarks/verified_recall.py → src/all41n14lla/engine/retrieval.py
- `main()` --calls--> `default_db_path()`  [INFERRED]
  benchmarks/verified_recall.py → src/all41n14lla/engine/storage.py

## Import Cycles
- None detected.

## Communities (37 total, 8 thin omitted)

### Community 0 - "MemoryNode"
Cohesion: 0.07
Nodes (53): Any, MemoryNode, Path, _age_days(), _constraint_floor(), _decay(), datetime, Per-type retrieval policies — the deterministic constraint floor + typed rescori (+45 more)

### Community 1 - "wire_all"
Cohesion: 0.10
Nodes (41): _backup(), Client, known_clients(), Path, Wire the all41n14lla MCP server into installed LLM clients.  ``all41n14lla wire`, Copy the config aside before the first modifying write., A ``[mcp_servers.all41n14lla]`` table as TOML text.      ``json.dumps`` is used, Detect every known client under ``home`` and wire each detected one.      Return (+33 more)

### Community 2 - "cli.py"
Cohesion: 0.09
Nodes (34): Enum, consolidate(), _default_vault(), doctor(), _doctor_constraint_floor(), forget(), init(), inspect() (+26 more)

### Community 3 - "VaultEventHandler"
Cohesion: 0.15
Nodes (22): BaseObserver, FileSystemEvent, FileSystemEventHandler, SimpleNamespace, Path, Live vault reconciliation via watchdog.  When the MCP server runs, a VaultObserv, Start a recursive observer on the vault. Returns the observer (or None     if th, Reconciles filesystem changes in the vault into the SQLite index. (+14 more)

### Community 4 - "Storage"
Cohesion: 0.14
Nodes (15): Connection, Row, Path, Scan vault folders, reindex every valid file, drop rows whose files vanished., Increment pairwise edge weights for a list of co-occurring node ids.          Pa, Context-managed wrapper around the SQLite index., Storage, _make_vault() (+7 more)

### Community 5 - "search"
Cohesion: 0.12
Nodes (23): FTS5 search over the nodes index.  Returns ranked (MemoryNode, score) pairs. The, Quote each term as its own FTS5 phrase, joined by ``OR`` (recall-oriented)., Return (node, score) pairs ranked by FTS5 relevance. Higher score = better match, _sanitize(), search(), Path, Tests for FTS5 query sanitization and multi-word search semantics.  Regression s, THE regression: the README quickstart example must return its note. (+15 more)

### Community 6 - "CliRunner"
Cohesion: 0.14
Nodes (18): CliRunner, Smoke tests for the Typer CLI., CLI default vault follows $ALL41N14LLA_VAULT, matching the MCP server., Without the env var, the CLI default is the ~/.all41n14lla dotfile., Path, End-to-end CLI regression for the README "First run" block.  The install-frictio, init → remember → recall, exactly as README.md documents it., The MCP server's recall tool rides the same code path — prove it too. (+10 more)

### Community 7 - "server.py"
Cohesion: 0.16
Nodes (19): Run the MCP stdio server., serve(), consolidate(), forget(), inspect(), main(), Path, all41n14lla MCP server (stdio transport).  Exposes ``remember``, ``recall``, ``f (+11 more)

### Community 8 - "default_db_path"
Cohesion: 0.21
Nodes (16): Constraint-recall benchmark: the deterministic floor vs pure BM25.  The question, run(), default_db_path(), folder_for(), SQLite index for all41n14lla.  Markdown files on disk are the canonical source o, Canonical index location for a given vault., Return the plural folder name for a NodeType., storage() (+8 more)

### Community 9 - "Part I — Power that compounds (the self-improving core)"
Cohesion: 0.11
Nodes (17): 1. One command, every client, 1. Use-strengthened recall (Hebbian ranking), 2. Pathway learning (the associative signature), 2. Warm start (kill the cold-start, deliver day-one wow), 3. Automatic sleep (consolidation as a rhythm, not a command), 3. The visceral demo (cross-agent continuity), 4. See your brain grow, 4. The two hemispheres audit each other (from TWO-BRAINS.md) (+9 more)

### Community 10 - "Changelog"
Cohesion: 0.12
Nodes (15): [0.1.0] - 2026-04-25, [0.1.0a1] - 2026-04-24, [0.1.0a2] - 2026-04-24, Added, Added, Added, Changed, Changed (+7 more)

### Community 11 - "The 60-second run"
Cohesion: 0.14
Nodes (13): Beat 1 — Install (10 sec), Beat 2 — Scaffold the vault (5 sec), Beat 3 — Remember something (8 sec), Beat 4 — Recall it (5 sec), Beat 5 — Switch to Claude Desktop (15 sec), Beat 6 — Recall from the other side (8 sec), Beat 7 — Prove it's on disk (9 sec), Before you hit record (+5 more)

### Community 12 - "test_server.py"
Cohesion: 0.26
Nodes (12): _make_vault(), Path, Smoke tests for the MCP server module.  Full protocol-level tests (stdio handsha, Importing the server should register the FastMCP tools without errors., scratch_vault(), test_consolidate_returns_stub_status(), test_forget_removes_file_and_index_row(), test_forget_reports_ambiguous_prefix() (+4 more)

### Community 13 - "test_verify.py"
Cohesion: 0.27
Nodes (12): _explode(), _make_vault(), Path, Tests for the opt-in verified-recall post-filter (engine/verify.py).  The judge, Default recall never touches the verifier and returns no `verified` key., The constraint floor is a deterministic guarantee — verify can't veto it., scratch_vault(), test_empty_results_short_circuit() (+4 more)

### Community 14 - "Savant cognition as memory architecture"
Cohesion: 0.17
Nodes (12): Finding 1: Typed memory works better than flat memory, Finding 2: Graph-backed memory is powerful but heavy, Finding 3: Pattern-indexed retrieval beats keyword matching, Finding 4: Memory needs to persist where the user can audit it, Further reading, LLMs are not memory systems, Savant cognition as memory architecture, The big idea (+4 more)

### Community 15 - "FIXES — 2026-06-10 night shift"
Cohesion: 0.18
Nodes (10): Bonus — stale "phrase search" claim in comparison doc, File inventory, Finding 1 (BLOCKER) — multi-word recall returned "No matches.", Finding 2 (BLOCKER) — three wrong test counts in two files, Finding 3 (HIGH) — Gemini CLI and Codex CLI had zero wiring docs, Finding 4 (HIGH) — install exceeded the 3-step rule → one-command goal, Finding 5 (MEDIUM) — hard-coded python3.13 + missing 3.14 classifier, Finding 6 (LOW) — missing multi-word recall regression test (+2 more)

### Community 16 - "Proposed, not done"
Cohesion: 0.18
Nodes (10): Audit corrections worth recording, J-taps (your hands, in order), P1 — Rewrite `wire`'s TOML handling if Codex wiring grows, P2 — `wire --unwire` / `wire --remove`, P3 — Windows/Linux client-path verification, P4 — `ruff` is still `continue-on-error: true` in CI, P5 — Benchmark README claim will drift the same way test counts did, P6 — Repo hygiene: build artifacts in git status (+2 more)

### Community 17 - "all41n14lla"
Cohesion: 0.18
Nodes (11): all41n14lla, Client config, Comparison, Docs, First run, How it works, Install, License (+3 more)

### Community 19 - "Quickstart — Claude Desktop"
Cohesion: 0.20
Nodes (10): 1. Install the CLI, 2. Create your vault, 3. Verify the engine works from the CLI, 4. Wire Claude Desktop, 5. Restart Claude Desktop, 6. Confirm it's connected, 7. Use it, Quickstart — Claude Desktop (+2 more)

### Community 20 - "verify_hits"
Cohesion: 0.25
Nodes (7): main(), Bench: does `recall(verify=True)` actually improve precision, or just cost laten, _judge(), Opt-in recall post-filter: judge each hit's relevance with a local model.  jcode, True = keep. Unparseable answers keep the hit (drop only on a clear no)., Filter recall hit dicts through the local judge.      Returns ``(hits, verified), verify_hits()

### Community 21 - "Contributing"
Cohesion: 0.22
Nodes (8): Contributing, Getting set up, Making a change, Reporting bugs, Scope and philosophy, Security, What doesn't get merged, What gets merged

### Community 22 - "Architecture"
Cohesion: 0.22
Nodes (9): Architecture, Concurrency, Four node types, Frontmatter schema, MCP server, Pathways, Retrieval flow, Storage (+1 more)

### Community 23 - "The Last Version — how a self-improving system escapes versioning"
Cohesion: 0.29
Nodes (6): Move A — A kernel small enough to finish (the TeX/SQLite move), Move B — Behavior lives in data (the constitutional move), Move C — The mechanic lives in the car (the 2026 move), The immortality floor (what "final" honestly guarantees), The Last Version — how a self-improving system escapes versioning, The three layers of improvement

### Community 24 - "What is all41n14lla? (the say-it-out-loud card)"
Cohesion: 0.33
Nodes (5): 10 seconds, 2 minutes — what makes it different from every other memory tool, 30 seconds, One-liners for specific rooms, What is all41n14lla? (the say-it-out-loud card)

### Community 25 - "The Two-Brain Architecture (v0.2 direction)"
Cohesion: 0.33
Nodes (5): Honesty footnote (for the précis-minded), Prior art in-house (verified 2026-07-10 — consolidate, don't invent), The idea, precisely, The Two-Brain Architecture (v0.2 direction), v0.2 build outline (fresh-session work, not tonight)

### Community 26 - "Why all41n14lla"
Cohesion: 0.33
Nodes (6): Memory does not belong inside the model, The five problems, The portable contract: markdown plus MCP, Where this goes, Why all41n14lla, Why four node types

### Community 27 - "Comparison"
Cohesion: 0.40
Nodes (5): Benchmark — constraint recall under noise, Comparison, Matrix, Notes per tool, When to use which

### Community 28 - "pull_request_template.md"
Cohesion: 0.40
Nodes (4): Checklist, Tests, What this PR does, Why

## Knowledge Gaps
- **127 isolated node(s):** `all41n14lla`, `What this PR does`, `Why`, `Tests`, `Checklist` (+122 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `default_db_path()` connect `default_db_path` to `MemoryNode`, `cli.py`, `VaultEventHandler`, `Storage`, `CliRunner`, `server.py`, `test_server.py`, `test_verify.py`, `verify_hits`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `Storage` connect `Storage` to `MemoryNode`, `cli.py`, `VaultEventHandler`, `search`, `server.py`, `default_db_path`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `verify_hits()` connect `verify_hits` to `wire_all`, `server.py`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `MemoryNode` (e.g. with `run()` and `remember()`) actually correct?**
  _`MemoryNode` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Storage` (e.g. with `RetrievalResult` and `MemoryNode`) actually correct?**
  _`Storage` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `default_db_path()` (e.g. with `run()` and `main()`) actually correct?**
  _`default_db_path()` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `retrieve()` (e.g. with `run()` and `main()`) actually correct?**
  _`retrieve()` has 17 INFERRED edges - model-reasoned connections that need verification._