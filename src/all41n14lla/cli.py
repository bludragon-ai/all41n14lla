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
) -> None:
    """Scaffold a new memory vault."""
    path = _resolve_vault(path)
    if path.exists() and any(path.iterdir()):
        console.print(
            f"[yellow]⚠ {path} exists and is not empty. Refusing to overwrite.[/yellow]"
        )
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
    console.print(f"[green]✓ Vault initialized at {path}[/green]")


@app.command()
def serve() -> None:
    """Run the MCP stdio server."""
    from all41n14lla.server import main

    main()


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
    node_id: str,
    confirm: bool = typer.Option(
        False, "--yes", "-y", help="Skip the confirmation prompt"
    ),
    vault: Path = _vault_option(),
) -> None:
    """Delete a memory by id (first 8 chars of uuid, or full id)."""
    vault = _resolve_vault(vault)
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
        storage.delete_node(target_id)
    if target_path.exists():
        target_path.unlink()
    console.print(f"[green]✓ Forgot[/green] {target_id[:8]}")


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
