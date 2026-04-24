"""all41n14lla CLI — Typer app."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from all41n14lla import __version__
from all41n14lla.engine.nodes import MemoryNode, NodeType
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

DEFAULT_VAULT = Path.home() / ".all41n14lla"
REQUIRED_DEPS = ("mcp", "typer", "yaml", "frontmatter", "watchdog", "rich")


def _vault_option() -> Path:
    return typer.Option(
        DEFAULT_VAULT,
        "--vault",
        "-v",
        help="Vault directory. Default: ~/.all41n14lla/ (hidden).",
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
    link_list = [l.strip() for l in links.split(",") if l.strip()]

    node = MemoryNode(
        type=nt, content=content, tags=tag_list, links=link_list
    )
    file_path = vault / folder_for(nt) / f"{node.id}.md"
    node.write(file_path)

    with Storage(default_db_path(vault)) as storage:
        storage.upsert_node(node)

    console.print(
        f"[green]✓ Remembered[/green] {nt.value}/{node.id[:8]} — {file_path}"
    )


@app.command()
def recall(
    query: str,
    node_type: Optional[str] = typer.Option(
        None, "--type", help="Restrict to a node type"
    ),
    limit: int = typer.Option(10, "--limit", help="Max results"),
    vault: Path = _vault_option(),
) -> None:
    """Search memories by full-text query."""
    vault = _resolve_vault(vault)
    nt = _resolve_type(node_type) if node_type else None

    with Storage(default_db_path(vault)) as storage:
        results = fts_search(storage, query, node_type=nt, limit=limit)

    if not results:
        console.print("[yellow]No matches.[/yellow]")
        return

    table = Table(title=f'Results for "{query}"', show_lines=False)
    table.add_column("score", justify="right")
    table.add_column("type")
    table.add_column("id", overflow="fold")
    table.add_column("preview", overflow="fold")
    for node, score in results:
        preview = node.content.strip().splitlines()[0][:80] if node.content else ""
        table.add_row(
            f"{score:.2f}", node.type.value, node.id[:8], preview
        )
    console.print(table)


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
    with Storage(default_db_path(vault)) as storage:
        rows = storage.conn.execute(
            "SELECT id, path FROM nodes WHERE id LIKE ?", (f"{node_id}%",)
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
def inspect(query: str) -> None:
    """Show nodes, edges, neighbors. (Stub — full impl in v0.1 final.)"""
    console.print(f"[yellow]STUB[/yellow]: inspect '{query}' — coming in v0.1 final")


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
def version() -> None:
    """Show version."""
    console.print(f"all41n14lla {__version__}")


if __name__ == "__main__":
    app()
