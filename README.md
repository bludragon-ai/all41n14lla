# all41n14lla

Portable memory for AI agents. Markdown on your disk. Speaks MCP.

> **Status:** `0.1.0-alpha` — scaffold only. Full README (demo GIF, thesis, comparison table) lands with the v0.1.0 release.

## Install

```bash
pipx install all41n14lla
all41n14lla init          # scaffolds ~/.all41n14lla/ (hidden, by default)
all41n14lla doctor        # verify environment
all41n14lla serve         # run MCP stdio server
```

The default vault path is `~/.all41n14lla/` — a hidden dotfile, conventional for per-user app data. Use `--path ~/memory` or any other path if you prefer a visible vault (e.g., one you open in Obsidian).

## Four node types

- `concepts/` — stable ideas
- `patterns/` — repeated behaviors
- `episodes/` — specific events
- `constraints/` — hard rules

Each memory is a markdown file with YAML frontmatter. You can edit them by hand.

## Claude Code / Desktop config

```json
{
  "mcpServers": {
    "all41n14lla": {
      "command": "all41n14lla",
      "args": ["serve"]
    }
  }
}
```

## Docs

- [Origin](ORIGIN.md) — where the name comes from
- [Why](docs/why.md) — the thesis
- [Architecture](docs/architecture.md) — how it works
- [Comparison](docs/comparison.md) — vs. Basic Memory, MemPalace, mem0, official MCP Memory

## License

MIT © Jordan Truong
