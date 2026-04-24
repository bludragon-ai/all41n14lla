# Demo script (60-second GIF)

Exact sequence for recording the `v0.1.0` demo GIF. Aim for ~60 seconds of screen time; target file size < 5 MB for GitHub README rendering.

## Before you hit record

1. **Uninstall + reinstall** so the demo starts from a clean state:
   ```bash
   pipx uninstall all41n14lla 2>/dev/null; true
   rm -rf ~/.all41n14lla
   ```
2. **Enlarge terminal font** (⌘+ a few times in your terminal app) — GIFs compress small, and people watching on mobile can't read tiny text.
3. **Set terminal to ~90 columns wide.** Wider wraps badly in the GIF.
4. **Close unrelated apps.** Just terminal + Claude Desktop on screen.
5. **Pre-open Claude Desktop** to a new, empty chat.
6. **Have `claude_desktop_config.json` ready to open** (you'll show the config briefly).

## Capture tool

macOS QuickTime:
1. Open QuickTime Player.
2. File → New Screen Recording (⌃⌘N).
3. Choose "Record Selected Portion" and drag a rectangle around the terminal. Keep Claude Desktop visible if you want the split-screen look.
4. Record.
5. Export → 480p or 720p MP4.
6. Convert to GIF with `ffmpeg` or `gifski`:
   ```bash
   ffmpeg -i demo.mov -vf "fps=15,scale=900:-1:flags=lanczos" -loop 0 docs/demo.gif
   # or, for higher quality:
   gifski --fps 15 --width 900 -o docs/demo.gif demo.mov
   ```

## The 60-second run

### Beat 1 — Install (10 sec)

Type this slowly enough to read on pause:

```bash
pipx install --pip-args='--pre' all41n14lla
```

Let the install finish. The `installed package all41n14lla 0.1.0a2` line should be visible in the recording.

### Beat 2 — Scaffold the vault (5 sec)

```bash
all41n14lla init
ls ~/.all41n14lla/
```

Viewers see the four folders (`concepts`, `patterns`, `episodes`, `constraints`) created.

### Beat 3 — Remember something (8 sec)

```bash
all41n14lla remember constraint "Never commit secrets to git"
```

The green `✓ Remembered constraint/...` line lands.

### Beat 4 — Recall it (5 sec)

```bash
all41n14lla recall "secrets"
```

Results table renders, showing the constraint row with its preview.

### Beat 5 — Switch to Claude Desktop (15 sec)

Click into Claude Desktop's new chat. Type (or paste) this message:

> Remember this as a concept: all41n14lla uses SQLite FTS5 under the hood.

Claude replies confirming it called the `remember` tool. You'll see the tool call flash by in the UI.

### Beat 6 — Recall from the other side (8 sec)

Still in Claude Desktop, new message:

> What did I tell you about all41n14lla's storage?

Claude responds by calling `recall` and summarizing the concept.

### Beat 7 — Prove it's on disk (9 sec)

Switch back to the terminal:

```bash
ls ~/.all41n14lla/concepts/
cat ~/.all41n14lla/concepts/*.md | head -20
```

Two files now (one from the CLI `remember`, one from Claude Desktop), both plain markdown with YAML frontmatter. Close with this keystroke visible.

Total: ~60 seconds.

## Voice-over / caption track (optional)

If you want captions baked into the GIF, keep them brief. Example text overlays per beat:

1. "Install from PyPI"
2. "Scaffold a vault"
3. "Remember from the CLI"
4. "Recall what you saved"
5. "Claude Desktop can write too"
6. "…and read back what Claude wrote"
7. "It's all just markdown on your disk"

## Once the GIF is done

1. Save it as `docs/demo.gif` in the repo.
2. Run `du -h docs/demo.gif` — confirm it's under 5 MB.
3. Open the `README.md` in a Markdown preview to verify it renders.
4. Commit: `git add docs/demo.gif README.md && git commit -m "Add demo GIF for v0.1.0 release"`.
5. Cut the v0.1.0 (non-alpha) release: bump `pyproject.toml` + `__init__.py` version to `0.1.0`, update CHANGELOG, tag `v0.1.0`, push.

The GIF is the unblocker for the LinkedIn post. Bake for 24 hours after that, then post.
