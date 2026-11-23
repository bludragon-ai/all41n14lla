"""all41n14lla CLI — Typer app."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

import typer
from rich.console import Console
from rich.table import Table

from all41n14lla import __version__
from all41n14lla.engine.nodes import MemoryNode, NodeType
from all41n14lla.engine.retrieval import retrieve
from all41n14lla.engine.search import search as fts_search
from all41n14lla.engine.storage import (
    NODE_FOLDERS,
    Storage,
    default_db_path,
    folder_for,
)
from all41n14lla.persona import Persona, persona_text, write_persona
from all41n14lla.reincarnate import QUESTIONS, load_answers
from all41n14lla.reincarnate import reincarnate as _reincarnate

app = typer.Typer(
    name="all41n14lla",
    help="Portable memory for AI agents. Markdown on your disk. Speaks MCP.",
    no_args_is_help=True,
)
console = Console()

def _default_vault() -> Path:
    """Default vault: ``$ALL41N14LLA_VAULT`` if set, else ``~/.all41n14lla/``.

    Mirrors the MCP server's resolution (``server.py:_vault_path``) so the CLI
    and the server agree on which vault they read when no ``--vault`` is passed.
    Without this, ``doctor``/``recall``/etc. silently read the empty dotfile
    even when the server is pointed at a real vault via the env var.
    """
    env = os.environ.get("ALL41N14LLA_VAULT")
    return Path(env) if env else Path.home() / ".all41n14lla"


DEFAULT_VAULT = _default_vault()
REQUIRED_DEPS = ("mcp", "typer", "yaml", "frontmatter", "watchdog", "rich")


def _vault_option() -> Path:
    return typer.Option(
        DEFAULT_VAULT,
        "--vault",
        "-v",
        help="Vault directory. Defaults to $ALL41N14LLA_VAULT, else ~/.all41n14lla/.",
    )


def _resolve_vault(vault: Path) -> Path:
    return vault.expanduser().resolve()


def _resolve_type(name: str) -> NodeType:
    try:
        return NodeType(name.lower())
    except ValueError:
        valid = ", ".join(t.value for t in NodeType)
        console.print(f"[red]Unknown type '{name}'. Valid: {valid}[/red]")
        raise typer.Exit(1)


@app.command()
def init(
    path: Path = typer.Option(
        DEFAULT_VAULT,
        "--path",
        "-p",
        help="Where to create the vault. Default: ~/.all41n14lla/ (hidden dotfile).",
    ),
    name: str = typer.Option(
        None, "--name", help="Optional: give the AI a persona name (writes PERSONA.md)."
    ),
    address: str = typer.Option(
        None, "--address", help="Optional: how the persona should address you. Requires --name."
    ),
    tone: str = typer.Option(
        None, "--tone", help="Optional: the persona's tone, e.g. 'warm and direct'. Requires --name."
    ),
) -> None:
    """Scaffold a new memory vault. Add --name/--address/--tone for an optional persona."""
    path = _resolve_vault(path)
    if path.exists() and any(path.iterdir()):
        console.print(
            f"[yellow]⚠ {path} exists and is not empty. Refusing to overwrite.[/yellow]"
        )
        raise typer.Exit(1)

    persona_fields = {"name": name, "address": address, "tone": tone}
    provided = {k: v for k, v in persona_fields.items() if v}
    if provided and len(provided) != 3:
        missing = ", ".join(f"--{k}" for k, v in persona_fields.items() if not v)
        console.print(f"[red]A persona needs all three flags. Missing: {missing}[/red]")
        raise typer.Exit(1)

    for folder in NODE_FOLDERS:
        (path / folder).mkdir(parents=True, exist_ok=True)
    (path / ".all41n14lla").mkdir(exist_ok=True)
    (path / "README.md").write_text(
        "# Your all41n14lla vault\n\n"
        "Four folders, four types of memory:\n\n"
        "- `concepts/` — stable ideas\n"
        "- `patterns/` — repeated behaviors\n"
        "- `episodes/` — specific events\n"
        "- `constraints/` — hard rules\n\n"
        "Drop markdown files with YAML frontmatter anywhere. The MCP server indexes them.\n",
        encoding="utf-8",
    )
    # Touch the index so `doctor` reports it healthy even before the first write.
    with Storage(default_db_path(path)):
        pass

    if provided:
        write_persona(path, Persona(name=name, address=address, tone=tone))
        console.print(f"[green]✓ Vault initialized at {path} with persona '{name}'[/green]")
    else:
        console.print(f"[green]✓ Vault initialized at {path}[/green]")


@app.command()
def reincarnate(
    path: Path = typer.Option(
        DEFAULT_VAULT, "--path", "-p",
        help="Where the vault is born. Default: ~/.all41n14lla/ (must be empty).",
    ),
    answers: Path = typer.Option(
        None, "--answers", "-a",
        help="JSON file of answers (question key → text) for a non-interactive rebirth.",
    ),
    wire: bool = typer.Option(
        False, "--wire", help="After the rebirth, wire the vault into every MCP client on this machine.",
    ),
) -> None:
    """Interactive first-run: your last thoughts become the assistant's first skills."""
    if answers is not None:
        given = load_answers(answers)
    else:
        console.print("[dim]Your last thoughts decide what you wake up with. One line each; Enter skips.[/dim]\n")
        given = {}
        total = len(QUESTIONS)
        for i, q in enumerate(QUESTIONS, 1):
            console.print(f"[bold]{i}/{total}[/bold]  {q.prompt}  [dim]({q.hint})[/dim]")
            given[q.key] = typer.prompt("  ›", default="", show_default=False)
        console.print()
    try:
        _reincarnate(path, given, say=console.print)
    except FileExistsError as exc:
        console.print(f"[yellow]⚠ {exc}[/yellow]")
        raise typer.Exit(1)
    if wire:
        from all41n14lla import wire as wiring

        results = wiring.wire_all(vault=str(_resolve_vault(path)))
        if not results:
            console.print("[yellow]No known MCP clients detected — nothing wired.[/yellow]")
        for r in results:
            console.print(f"《Confirmed.》 {r.client}: {r.status} · {r.config}")


@app.command()
def devour(
    target: Path = typer.Argument(..., help="ONE file or directory to analyze."),
    accept: str = typer.Option(
        None, "--accept",
        help="Write candidates: 'all', or a list like '1,3,5' / '2-6'. Without it, nothing is written.",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Ask y/n for each candidate."
    ),
    max_files: int = typer.Option(200, "--max-files", help="Stop reading after this many files."),
    vault: Path = _vault_option(),
) -> None:
    """Predator: analyze one path and propose memories. Writes nothing until you accept."""
    from all41n14lla.devour import analyze, consume, existing_source_hashes, parse_accept

    vault = _resolve_vault(vault)
    if not vault.exists():
        console.print(f"[red]No vault at {vault}. Run `all41n14lla reincarnate` first.[/red]")
        raise typer.Exit(1)
    console.print(f"《Notice.》 Predator: analyzing {target} …")
    try:
        a = analyze(target, existing_source_hashes(vault), max_files=max_files)
    except FileNotFoundError:
        console.print(f"[red]No such path: {target}[/red]")
        raise typer.Exit(1)
    if not a.candidates:
        console.print(
            f"《Report.》 Nothing to gain. {a.files_read} file(s) read, {a.files_skipped} skipped, "
            f"{a.already_devoured} already devoured."
        )
        return
    table = Table(title=f"Predator — {len(a.candidates)} candidate(s) from {a.files_read} file(s)")
    table.add_column("#", justify="right")
    table.add_column("type")
    table.add_column("preview", overflow="fold")
    table.add_column("where", overflow="fold")
    for i, c in enumerate(a.candidates, 1):
        table.add_row(str(i), c.kind.value, (c.content[:110] + "…") if len(c.content) > 110 else c.content, c.where)
    console.print(table)
    if a.truncated:
        console.print(f"[yellow]Stopped at {max_files} files; raise --max-files to read more.[/yellow]")
    if interactive:
        picks = [i for i, c in enumerate(a.candidates, 1) if typer.confirm(f"  devour #{i} [{c.skill}]?", default=False)]
        if not picks:
            console.print("《Report.》 Nothing devoured.")
            return
        written = consume(vault, a, picks, say=console.print)
    elif accept is not None:
        try:
            picks = parse_accept(accept, len(a.candidates))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        written = consume(vault, a, picks, say=console.print)
    else:
        console.print(
            "《Report.》 Nothing devoured. Re-run with [bold]--accept all[/bold] or "
            "[bold]--accept 1,3,5[/bold] to consume, or [bold]-i[/bold] to choose one by one."
        )
        return
    console.print(f"《Report.》 {len(written) - 1} memories gained; the meal is episode {written[-1].id[:8]}.")


@app.command()
def evolve(vault: Path = _vault_option()) -> None:
    """What the assistant has become: counts, tier, and what that tier may do. Read-only."""
    from all41n14lla.evolve import evolution

    vault = _resolve_vault(vault)
    if not vault.exists():
        console.print(f"[red]No vault at {vault}.[/red]")
        raise typer.Exit(1)
    e = evolution(vault)
    table = Table(title="Evolution")
    table.add_column("memory")
    table.add_column("count", justify="right")
    for k in ("concepts", "patterns", "episodes", "constraints", "devoured"):
        table.add_row(k, str(getattr(e, k)))
    console.print(table)
    console.print(f"《Report.》 Tier: [bold]{e.tier}[/bold] — {e.allowed}.")
    if e.until_next is not None:
        console.print(f"{e.until_next} more episode(s) to the next tier.")


@app.command()
def persona(vault: Path = _vault_option()) -> None:
    """Print the vault's persona, if one has been set."""
    vault = _resolve_vault(vault)
    text = persona_text(vault)
    if text is None:
        console.print(
            "[yellow]No persona set for this vault.[/yellow] "
            "Run `all41n14lla init --name ... --address ... --tone ...` on a fresh vault, "
            "or write PERSONA.md into it directly."
        )
        raise typer.Exit(1)
    console.print(text)


@app.command()
def serve(
    repetition_guard: bool = typer.Option(
        True,
        "--repetition-guard/--no-repetition-guard",
        help="Cut detected output loops via the guard_output tool. On by default.",
    ),
    repetition_threshold: float = typer.Option(
        0.82, "--repetition-threshold", help="Similarity ratio (0-1) that counts as a repeat."
    ),
    repetition_window_chars: int = typer.Option(
        150, "--repetition-window-chars", help="Trailing-character window compared for similarity."
    ),
) -> None:
    """Run the MCP stdio server."""
    from all41n14lla.server import main

    main(
        repetition_guard=repetition_guard,
        repetition_threshold=repetition_threshold,
        repetition_window_chars=repetition_window_chars,
    )


def _doctor_constraint_floor(storage: Storage) -> None:
    """Report constraint-floor health: count, untagged rules, tag hotspots.

    The floor's guarantee is tag-scoped — an untagged constraint can never be
    floor-surfaced, and a tag shared by too many constraints will flood the
    caller's context (the floor caps at 50 and flags overflow). Make both
    observable instead of surprising.
    """
    from collections import Counter

    rows = storage.conn.execute(
        "SELECT path FROM nodes WHERE type = ?", (NodeType.CONSTRAINT.value,)
    ).fetchall()
    constraints: list[MemoryNode] = []
    for row in rows:
        p = Path(row["path"])
        if p.exists():
            try:
                constraints.append(MemoryNode.from_file(p))
            except (OSError, KeyError, ValueError, TypeError) as exc:
                logger.debug("skipping unparsable constraint %s: %s", p, exc)
                continue
    console.print(
        f"[green]✓[/green] constraint floor: ACTIVE ({len(constraints)} constraints indexed)"
    )
    # judge tags through the SAME tokenizer the engine uses — a tag of pure
    # symbols ("→", "++") is invisible to the floor even though frontmatter
    # technically has tags
    from all41n14lla.engine.retrieval import _tokenize

    def _floor_visible(c: MemoryNode) -> bool:
        return any(_tokenize(str(tag)) for tag in c.tags)

    untagged = [c for c in constraints if not _floor_visible(c)]
    if untagged:
        console.print(
            f"[yellow]⚠[/yellow] {len(untagged)} constraint(s) have no floor-visible tags — "
            "the floor is tag-scoped, so these can never be guaranteed-surfaced. "
            f"First: {untagged[0].id[:8]}"
        )
    tag_counts = Counter(
        str(tag).lower() for c in constraints for tag in c.tags
    )
    hot = [(t, n) for t, n in tag_counts.most_common() if n > 20]
    for tag, n in hot:
        console.print(
            f"[yellow]⚠[/yellow] tag hotspot: '{tag}' is on {n} constraints — "
            "recalls overlapping it approach the floor cap (50); consider splitting"
        )


@app.command()
def doctor(vault: Path = _vault_option()) -> None:
    """Check environment + vault health."""
    from importlib.util import find_spec

    console.print(f"[bold]all41n14lla[/bold] v{__version__}")
    console.print(f"Python: {sys.version.split()[0]}")

    for mod in REQUIRED_DEPS:
        if find_spec(mod) is not None:
            console.print(f"[green]✓[/green] {mod}")
        else:
            console.print(f"[red]✗[/red] {mod} — missing")

    vault = _resolve_vault(vault)
    if vault.exists():
        console.print(f"[green]✓[/green] vault: {vault}")
        db = default_db_path(vault)
        if db.exists():
            with Storage(db) as storage:
                count = storage.conn.execute(
                    "SELECT COUNT(*) FROM nodes"
                ).fetchone()[0]
                console.print(f"[green]✓[/green] index: {db} ({count} nodes)")
                _doctor_constraint_floor(storage)
        else:
            console.print(
                f"[yellow]⚠[/yellow] no index yet at {db} — run `remember` or `reconcile`"
            )
    else:
        console.print(
            f"[yellow]⚠[/yellow] no vault at {vault} — run `all41n14lla init`"
        )


@app.command()
def remember(
    node_type: str = typer.Argument(
        ..., metavar="TYPE", help="concept|pattern|episode|constraint"
    ),
    content: str = typer.Argument(..., help="The memory content"),
    tags: str = typer.Option("", "--tags", "-t", help="Comma-separated tags"),
    links: str = typer.Option(
        "", "--links", "-l", help="Comma-separated ids of related nodes"
    ),
    vault: Path = _vault_option(),
) -> None:
    """Write a new memory to the vault and index it."""
    vault = _resolve_vault(vault)
    if not vault.exists():
        console.print(
            f"[red]No vault at {vault}. Run `all41n14lla init` first.[/red]"
        )
        raise typer.Exit(1)

    nt = _resolve_type(node_type)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    link_list = [link.strip() for link in links.split(",") if link.strip()]

    node = MemoryNode(
        type=nt, content=content, tags=tag_list, links=link_list
    )
    file_path = vault / folder_for(nt) / f"{node.id}.md"
    node.write(file_path)

    with Storage(default_db_path(vault)) as storage:
        storage.upsert_node(node)
        if nt is NodeType.EPISODE and link_list:
            storage.increment_edges(link_list)

    console.print(
        f"[green]✓ Remembered[/green] {nt.value}/{node.id[:8]} — {file_path}"
    )


@app.command()
def recall(
    query: str,
    node_type: str | None = typer.Option(
        None, "--type", help="Restrict to a node type"
    ),
    limit: int = typer.Option(10, "--limit", help="Max results"),
    vault: Path = _vault_option(),
) -> None:
    """Search memories with type-aware retrieval (constraint floor + decay)."""
    vault = _resolve_vault(vault)
    nt = _resolve_type(node_type) if node_type else None

    with Storage(default_db_path(vault)) as storage:
        outcome = retrieve(storage, query, node_type=nt, limit=limit)

    if not outcome.results:
        console.print("[yellow]No matches.[/yellow]")
        return

    table = Table(title=f'Results for "{query}"', show_lines=False)
    table.add_column("score", justify="right")
    table.add_column("type")
    table.add_column("id", overflow="fold")
    table.add_column("preview", overflow="fold")
    for node, score in outcome.results:
        preview = node.content.strip().splitlines()[0][:80] if node.content else ""
        type_label = (
            f"[cyan]⚓ {node.type.value}[/cyan]"
            if node.id in outcome.floor_ids
            else node.type.value
        )
        table.add_row(f"{score:.2f}", type_label, node.id[:8], preview)
    console.print(table)
    if outcome.floor_ids:
        console.print(
            "[dim]⚓ = constraint floor — surfaced by tag overlap, exempt from ranking[/dim]"
        )
    if outcome.floor_overflow:
        console.print(
            "[yellow]⚠ constraint floor hit its safety cap — narrow your tags "
            "or split hot tags (see `doctor`)[/yellow]"
        )


@app.command()
def forget(
    node_id: str = typer.Argument(None, help="Node id (first 8 chars or full). Omit when using --source."),
    source: str = typer.Option(
        None, "--source", "-s",
        help="Erase every memory devoured from this source path (exact, prefix, or glob) and get a receipt.",
    ),
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Skip the confirmation prompt"
    ),
    vault: Path = _vault_option(),
) -> None:
    """Delete a memory by id, or every memory from a --source. Every erasure writes a receipt."""
    from all41n14lla.erase import erase, find_by_source

    vault = _resolve_vault(vault)
    if source:
        victims = find_by_source(vault, source)
        if not victims:
            console.print(f"[red]No memories carry source '{source}'.[/red]")
            raise typer.Exit(1)
        console.print(f"《Notice.》 {len(victims)} memor{'y' if len(victims) == 1 else 'ies'} from '{source}':")
        for n in victims:
            console.print(f"  {n.type.value:<10} {n.id[:8]}  {n.content[:70]}")
        if not confirm and not typer.confirm("Erase them?"):
            console.print("[yellow]Aborted. Nothing erased.[/yellow]")
            raise typer.Exit(0)
        r = erase(vault, victims, source=source)
        console.print(
            f"《Report.》 Erased {r.count}. Re-scan for '{source}': {r.remaining_after_rescan} remain. "
            f"Receipt: {r.path}"
        )
        return
    ident = (node_id or "").strip()
    if len(ident) < 8:
        console.print("[red]id must be at least the first 8 characters[/red]")
        raise typer.Exit(1)
    like = ident.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with Storage(default_db_path(vault)) as storage:
        rows = storage.conn.execute(
            "SELECT id, path FROM nodes WHERE id LIKE ? ESCAPE '\\'", (f"{like}%",)
        ).fetchall()
        if not rows:
            console.print(f"[red]No node matches '{node_id}'[/red]")
            raise typer.Exit(1)
        if len(rows) > 1:
            console.print(
                f"[red]Ambiguous — '{node_id}' matches {len(rows)} nodes. "
                "Use the full id.[/red]"
            )
            raise typer.Exit(1)
        target_id = rows[0]["id"]
        target_path = Path(rows[0]["path"])
        if not confirm:
            console.print(f"About to delete {target_id} at {target_path}")
            if not typer.confirm("Continue?"):
                console.print("[yellow]Aborted.[/yellow]")
                raise typer.Exit(0)
    node = MemoryNode.from_file(target_path) if target_path.exists() else None
    if node is None:
        with Storage(default_db_path(vault)) as storage:
            storage.delete_node(target_id)
        console.print(f"[green]✓ Forgot[/green] {target_id[:8]} (file was already gone)")
        return
    r = erase(vault, [node], source=None)
    console.print(f"[green]✓ Forgot[/green] {target_id[:8]} · receipt: {r.path}")


@app.command()
def inspect(
    query_or_id: str = typer.Argument(..., help="Node id (full or prefix) or search phrase"),
    vault: Path = _vault_option(),
) -> None:
    """Show a node's details plus its top co-occurrence neighbors."""
    vault = _resolve_vault(vault)
    with Storage(default_db_path(vault)) as storage:
        rows = storage.conn.execute(
            "SELECT id, path FROM nodes WHERE id LIKE ?", (f"{query_or_id}%",)
        ).fetchall()

        node: MemoryNode | None = None
        if len(rows) == 1:
            target_path = Path(rows[0]["path"])
            if target_path.exists():
                node = MemoryNode.from_file(target_path)
        else:
            hits = fts_search(storage, query_or_id, limit=1)
            if hits:
                node, _ = hits[0]

        if node is None:
            console.print(f"[yellow]No match for '{query_or_id}'[/yellow]")
            raise typer.Exit(1)

        edges = storage.conn.execute(
            """
            SELECT dst_id AS neighbor_id, weight FROM edges WHERE src_id = ?
            UNION
            SELECT src_id AS neighbor_id, weight FROM edges WHERE dst_id = ?
            ORDER BY weight DESC
            LIMIT 10
            """,
            (node.id, node.id),
        ).fetchall()

    console.print(f"[bold cyan]{node.type.value}[/bold cyan] {node.id}")
    if node.tags:
        console.print(f"[dim]tags:[/dim] {', '.join(node.tags)}")
    if node.links:
        console.print(f"[dim]links:[/dim] {', '.join(link[:8] for link in node.links)}")
    console.print()
    console.print(node.content.strip())

    if edges:
        console.print()
        table = Table(title="Neighbors (by edge weight)", show_lines=False)
        table.add_column("weight", justify="right")
        table.add_column("neighbor id")
        for row in edges:
            table.add_row(f"{float(row['weight']):.2f}", row["neighbor_id"][:8])
        console.print(table)
    else:
        console.print()
        console.print("[dim](no edges yet — write episodes with --links to build pathways)[/dim]")


@app.command()
def consolidate() -> None:
    """Promote patterns from episodes + apply decay."""
    console.print("[yellow]Pattern promotion coming in v0.2.0[/yellow]")


@app.command()
def reconcile(vault: Path = _vault_option()) -> None:
    """Re-scan the vault and rebuild the index to match disk."""
    vault = _resolve_vault(vault)
    if not vault.exists():
        console.print(f"[red]No vault at {vault}.[/red]")
        raise typer.Exit(1)
    with Storage(default_db_path(vault)) as storage:
        indexed, removed = storage.reconcile(vault)
    console.print(
        f"[green]✓ Reconciled[/green] — indexed {indexed} files, removed {removed} stale rows"
    )


@app.command()
def wire(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without writing anything."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace an existing all41n14lla entry that differs (JSON clients only).",
    ),
    command: str | None = typer.Option(
        None,
        "--command",
        help="Server command to write. Default: absolute path of the installed binary.",
    ),
    vault: Path | None = typer.Option(
        None,
        "--vault",
        "-v",
        help=(
            "Embed ALL41N14LLA_VAULT in each client config for a non-default vault. "
            "Defaults to $ALL41N14LLA_VAULT when set."
        ),
    ),
) -> None:
    """Detect installed MCP clients and wire the all41n14lla server into each.

    Knows Claude Code, Claude Desktop, Cursor, Gemini CLI, and Codex CLI.
    Idempotent — already-wired clients are left untouched. Configs are backed
    up next to the original before any modifying write. Conflicting entries
    are reported, never silently overwritten.
    """
    from all41n14lla import wire as wiring

    env_vault = os.environ.get("ALL41N14LLA_VAULT")
    vault_value = (
        str(_resolve_vault(vault)) if vault else (env_vault or None)
    )
    results = wiring.wire_all(
        command=command, vault=vault_value, dry_run=dry_run, force=force
    )

    if not results:
        console.print(
            "[yellow]No known MCP clients detected.[/yellow] Looked for Claude Code "
            "(~/.claude.json), Claude Desktop, Cursor (~/.cursor/), Gemini CLI "
            "(~/.gemini/), and Codex CLI (~/.codex/). See the README for manual config."
        )
        return

    styles = {
        wiring.WIRED: "[green]✓ wired[/green]",
        wiring.ALREADY: "[green]✓ already wired[/green]",
        wiring.WOULD_WIRE: "[cyan]→ would wire[/cyan]",
        wiring.CONFLICT: "[yellow]⚠ conflict[/yellow]",
        wiring.ERROR: "[red]✗ error[/red]",
    }
    table = Table(title="MCP client wiring" + (" (dry run)" if dry_run else ""))
    table.add_column("client")
    table.add_column("status")
    table.add_column("config", overflow="fold")
    table.add_column("detail", overflow="fold")
    for r in results:
        table.add_row(r.client, styles.get(r.status, r.status), str(r.config), r.detail)
    console.print(table)

    if any(r.status == wiring.WIRED for r in results):
        console.print(
            "[dim]Restart each client to load the server (MCP servers load on startup). "
            f"Backups of modified configs sit next to the originals as "
            f"*{wiring.BACKUP_SUFFIX}.[/dim]"
        )
    if any(r.status == wiring.ERROR for r in results):
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"all41n14lla {__version__}")


if __name__ == "__main__":
    app()
