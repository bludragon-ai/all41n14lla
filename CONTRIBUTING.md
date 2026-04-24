# Contributing

## Scope and philosophy

v0.1 ships the shape: four node types, markdown on disk, SQLite + FTS5 index, MCP stdio server. v0.2 adds the dynamics — embeddings, pattern promotion, decay. PRs that align with the roadmap (see [README](README.md)) are welcome. PRs that add features off the roadmap should open an issue first so we can agree on the shape before you spend time on it. No feature creep for its own sake.

## Getting set up

```bash
git clone https://github.com/bludragon-ai/all41n14lla.git
cd all41n14lla
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q        # should print 16 passed (or current count)
```

Python 3.11+ works; 3.13 is what I develop against.

## Making a change

One branch per PR. Name it `feat/short-name` or `fix/short-name`:

```bash
git checkout -b fix/recall-constraint-tag-overlap
```

Write the test before the fix. Run `pytest` and `ruff check src tests` locally before you open the PR.

## What gets merged

- Tests pass in CI.
- The diff is smaller than the justification for it.
- The change preserves the "markdown on disk = source of truth" invariant. The index is a cache; the files are canonical.
- The change preserves the four node types (concept, pattern, episode, constraint) as the public API. Adding a fifth is a roadmap conversation, not a PR.

## What doesn't get merged

- Scope creep into v0.2+: embeddings, pattern promotion from repeated episodes, cloud sync, Obsidian plugin. These are planned; they are not open for freelance PRs yet.
- New dependencies without a one-line justification in the PR description.
- Style-only diffs.
- Refactors without a behavioral benefit.
- Marketing copy in code comments or docs.

## Reporting bugs

Use the bug template: [.github/ISSUE_TEMPLATE/bug_report.yml](.github/ISSUE_TEMPLATE/bug_report.yml). Include the output of `all41n14lla doctor` when relevant.

## Security

If you find a vulnerability, email Jordan directly at emailme@jordantruong.com. Do not file a public issue.
