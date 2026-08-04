# PROPOSALS — 2026-06-10 night shift

Items NOT done tonight — either they need J's hands (outbound/publish), a
product decision, or they are structural enough to deserve daylight review.
Companion to `FIXES-2026-06-10.md`.

## J-taps (your hands, in order)

1. **Review the staged diff** — everything is uncommitted: `cd
   ~/Projects/all41n14lla && git diff` (+ 6 untracked files). The one
   semantics call made on your behalf: multi-word recall is now **AND**
   (all terms must appear, any position) instead of phrase-adjacency.
   FTS5's own default, easy to flip — see FIXES Finding 1.
2. **Commit** — suggested: one commit for the search fix + tests, one for
   `wire` + tests, one for docs/CI. Or a single `fix+feat` commit; your call.
3. **Release** — the README now documents `wire` and the recall fix, both
   honest-labeled "in main, unreleased". A PyPI release makes the labels
   removable and the badge truthful. Suggested version: **0.2.0** (new
   command + behavior change in recall matching = minor bump, not patch).
   Release motion: bump `pyproject.toml` version → update CHANGELOG heading
   → tag → push (trusted-publishing workflow does PyPI on tag push).
4. **`gh auth refresh`** — already queued from earlier tonight; needed
   before any push anyway.

## Proposed, not done

### P1 — Rewrite `wire`'s TOML handling if Codex wiring grows

Tonight's Codex path appends a validated `[mcp_servers.all41n14lla]` table
and refuses to rewrite an existing-but-different entry (stdlib has no TOML
writer; taking a `tomlkit` dependency for a convenience command violated the
no-new-deps bar tonight). If users hit the TOML conflict path in practice,
add `tomlkit` as an optional extra (`pip install all41n14lla[wire]`) and do
real in-place TOML edits. Decision needed: dependency vs. status quo.

### P2 — `wire --unwire` / `wire --remove`

Symmetry: a clean removal path for the server block. Deliberately skipped
tonight — it is a config-deleting operation and the night-shift law says no
new delete paths without your eyes. Straightforward to add behind an
explicit confirm.

### P3 — Windows/Linux client-path verification

`wire` carries path logic for win32 (`%APPDATA%/Claude`) and Linux
(`~/.config/Claude`) Claude Desktop, but only the macOS paths were verified
against a live machine tonight. CI runs Ubuntu and the wire tests pass
there by construction (fake homes), but a real Windows/Linux smoke before
advertising cross-platform `wire` would be honest.

### P4 — `ruff` is still `continue-on-error: true` in CI

`.github/workflows/test.yml:47` soft-fails lint. The tree is currently
ruff-clean (verified tonight), so flipping it to hard-fail costs nothing
now and prevents drift. One-line change; left for your tap since it changes
CI failure behavior for future contributors.

### P5 — Benchmark README claim will drift the same way test counts did

`README.md` comparison table hard-codes "measured 20/20 vs BM25's 1/20".
That number is benchmark-backed (fine today), but it is the same
hard-coded-claim pattern that produced Finding 2. Proposal: have
`benchmarks/constraint_recall.py` emit a one-line JSON artifact and a CI job
assert the README number matches it. Small, but it closes the lie-class
permanently.

### P6 — Repo hygiene: build artifacts in git status

`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, and
`src/all41n14lla.egg-info/` exist on disk; spot-check suggests they are
ignored, but `dist/` carrying 0.1.0 wheels in the working tree invites
confusion with released artifacts. Proposal: confirm `.gitignore` coverage
and clear stale wheels — deletion, so it waits for your explicit ok
(Deletion Policy).

## Audit corrections worth recording

- Finding 3 cited Codex config as `~/.codex/config.json`. Verified ground
  truth: `~/.codex/config.toml` (TOML, `mcp_servers` with underscore) — your
  own machine already runs all41n14lla through exactly that table.
- Finding 1's option (b) said stripping quotes entirely would give "FTS5's
  default OR behavior" — FTS5's implicit default for multiple terms is AND,
  not OR (and unsanitized input can inject query syntax / raise errors).
  The shipped fix gets the AND default *with* sanitization.
