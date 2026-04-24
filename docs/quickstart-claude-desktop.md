# Quickstart — Claude Desktop

This is the minimum path to get `all41n14lla` working in Claude Desktop on macOS. From nothing installed to "Claude can remember and recall for me" in under five minutes.

## 1. Install the CLI

```bash
pipx install --pip-args='--pre' all41n14lla
```

The `--pre` flag tells `pipx` to install pre-release versions — `all41n14lla` is currently in alpha, so this is required. Once `v0.1.0` ships as a stable release, you can drop `--pre`.

Verify the install:

```bash
all41n14lla version
# -> all41n14lla 0.1.0a2 (or newer)
```

## 2. Create your vault

```bash
all41n14lla init
```

This scaffolds `~/.all41n14lla/` — a hidden dotfile vault in your home directory. Inside it, four folders (`concepts/`, `patterns/`, `episodes/`, `constraints/`) and a SQLite index at `.all41n14lla/index.db`.

Want a visible vault you can open in Obsidian instead? Pass `--path`:

```bash
all41n14lla init --path ~/Documents/memory
```

Then always pass `--vault ~/Documents/memory` to subsequent CLI commands, or set the env var once:

```bash
export ALL41N14LLA_VAULT=~/Documents/memory
```

## 3. Verify the engine works from the CLI

Before wiring Claude Desktop, make sure the engine itself is healthy:

```bash
all41n14lla remember concept "Claude Desktop speaks MCP over stdio"
all41n14lla recall "MCP"
all41n14lla doctor
```

You should see the concept come back from `recall`, and `doctor` should show all dependencies ✓ and report the vault + index.

## 4. Wire Claude Desktop

Open Claude Desktop's MCP config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

If the file doesn't exist yet, create it. If it does, merge the `mcpServers` block into the existing JSON. The minimum config:

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

If you used a custom vault path in step 2, add an `env` field:

```json
{
  "mcpServers": {
    "all41n14lla": {
      "command": "all41n14lla",
      "args": ["serve"],
      "env": {
        "ALL41N14LLA_VAULT": "/Users/YOUR_USER/Documents/memory"
      }
    }
  }
}
```

## 5. Restart Claude Desktop

Fully quit (⌘Q) and reopen. Claude Desktop only loads MCP servers on startup.

## 6. Confirm it's connected

In a new Claude Desktop chat, paste this:

> What MCP tools do you have access to?

You should see Claude list `remember`, `recall`, `forget`, `inspect`, and `consolidate` under the `all41n14lla` server. If you don't, the server didn't connect — jump to **Troubleshooting** below.

## 7. Use it

Try these in a chat with Claude Desktop:

> Remember this as a constraint: never commit code with --no-verify.

> Recall what I said about committing code.

> Inspect the memory about commits.

The constraint goes into `~/.all41n14lla/constraints/` as a markdown file. Open that file in any editor — you can read it, edit it, delete it. Claude Desktop will pick up your hand edits live (watchdog observer is running inside the server).

## Troubleshooting

**`command not found: all41n14lla` inside Claude Desktop.** Claude Desktop uses a restricted PATH. Edit your config to use the full path instead of just `all41n14lla`:

```bash
which all41n14lla
# e.g. /Users/YOUR_USER/.local/bin/all41n14lla
```

Then in the config:

```json
{
  "mcpServers": {
    "all41n14lla": {
      "command": "/Users/YOUR_USER/.local/bin/all41n14lla",
      "args": ["serve"]
    }
  }
}
```

**Server starts but tools don't appear.** Restart Claude Desktop fully (⌘Q, reopen). MCP servers only load on cold start.

**`no vault at ~/.all41n14lla`.** You skipped step 2. Run `all41n14lla init` before `serve`.

**Tools appear but every call errors.** Run `all41n14lla doctor` from your terminal to confirm the vault is healthy. If the index is corrupted, `all41n14lla reconcile` rebuilds it from the markdown files on disk (which are the source of truth — the index is disposable).

**Logs.** Claude Desktop's MCP server logs live at `~/Library/Logs/Claude/mcp-server-all41n14lla.log`. Tail that for stderr output if something's weird.

## Same flow for Cursor / Claude Code

The MCP config format is the same. Cursor lives at `~/.cursor/mcp.json`. Claude Code uses `~/.claude.json` under the `mcpServers` key. Drop in the same server block and the same memories are available across all three tools — that's the whole point.
