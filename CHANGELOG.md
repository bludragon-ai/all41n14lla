# Changelog

All notable changes to `all41n14lla` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes yet.

## [0.1.0] - 2026-04-25

First stable release. Drops the alpha tag — `pipx install all41n14lla` now works without the `--pre` flag.

### Fixed
- Pinned `httpx>=0.27,<1` in project dependencies. Without this pin, `pipx install --pip-args='--pre' all41n14lla` (the alpha install path) cascaded the `--pre` flag to every transitive dependency and pulled `httpx 1.0.dev3`, which removed `httpx.TransportError` from its top-level namespace and crashed `mcp` import via `httpx_sse`. Stable installs from `0.1.0` onward don't need `--pre`, but the pin also defends future alpha installs against the same trap.

### Changed
- Project graduates from alpha to stable. No API or behavior changes versus `0.1.0a2` other than the dependency pin above.

## [0.1.0a2] - 2026-04-24

Integrity-fix alpha. Closes the watchdog + pathways gaps from `0.1.0a1` so the docs match the implementation exactly.

### Added
- Watchdog observer runs inside `serve` — hand-edits to vault markdown files sync into the index live. New module: `all41n14lla.watcher`.
- `remember episode ... --links a,b,c` increments pathways edge weights for each co-occurring id pair. New method: `Storage.increment_edges`.
- `inspect <query_or_id>` CLI command wired to the engine (accepts either a node id prefix or a search phrase, renders node + top-10 edge neighbors).
- `keywords` field in `pyproject.toml` for PyPI search discoverability; additional classifiers (`Intended Audience`, `Topic`, `Operating System`).
- GitHub Actions CI: test matrix on Python 3.11 / 3.12 / 3.13 (Ubuntu), plus `ruff check` (soft fail for now). Trusted-publishing workflow for PyPI on tag push.
- CI + PyPI + Python + License badges in README.
- `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/pull_request_template.md`.
- Tests: `test_pathways.py` (4 tests), `test_watcher.py` (6 tests). Suite now runs 26 tests.

### Changed
- `Storage` imports `datetime` / `timezone` to stamp edge rows.
- Documentation claims about live watchdog reconciliation and pathways auto-increment now match reality; no soft-walk needed.

### Fixed
- n/a (this release closes documented gaps rather than fixing regressions).

## [0.1.0a1] - 2026-04-24

First public alpha. Shipped to PyPI and GitHub Releases.

### Added
- Four node types: `concept`, `pattern`, `episode`, `constraint`. Each stored as a markdown file with YAML frontmatter in its own folder (`concepts/`, `patterns/`, `episodes/`, `constraints/`).
- SQLite index with FTS5 virtual table over content + tags (Porter tokenizer, BM25 ranking).
- Edges table for co-occurrence pathways (table only — auto-increment ships in 0.1.0a2).
- MCP stdio server exposing five tools: `remember`, `recall`, `forget`, `inspect`, `consolidate`.
- CLI entry point `all41n14lla` with commands `init`, `serve`, `doctor`, `remember`, `recall`, `forget`, `reconcile`, `version`. `inspect` and `consolidate` are stubs in this release.
- Default vault path `~/.all41n14lla/` (hidden dotfile); configurable via `--path` on `init` or `ALL41N14LLA_VAULT` env var on `serve`.
- Documentation: README, `docs/why.md`, `docs/architecture.md`, `docs/comparison.md`, `docs/savant-cognition.md`, `ORIGIN.md`.
- 16 automated tests covering nodes, CLI, storage lifecycle, search, and MCP server smoke paths.

### Known issues
- `watchdog` library is a dependency but the live observer is not wired into `serve` yet (ships in `0.1.0a2`). Use `all41n14lla reconcile` after hand-editing files until then.
- Pathways edges table exists but writes are not yet auto-incremented on `remember` calls. `consolidate` is stubbed.
- No embeddings — retrieval is lexical only. Semantic recall lands in `v0.2`.
- Tested on Python 3.13.13 on macOS arm64; other platforms via CI matrix as of `0.1.0a2`.

[Unreleased]: https://github.com/bludragon-ai/all41n14lla/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bludragon-ai/all41n14lla/releases/tag/v0.1.0
[0.1.0a2]: https://github.com/bludragon-ai/all41n14lla/releases/tag/v0.1.0a2
[0.1.0a1]: https://github.com/bludragon-ai/all41n14lla/releases/tag/v0.1.0a1
