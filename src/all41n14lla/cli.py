"""all41n14lla CLI — Typer app."""
from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from all41n14lla import __version__

app = typer.Typer(
    name="all41n14lla",
    help="Portable memory for AI agents. Markdown on your disk. Speaks MCP.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_VAULT = Path.home() / ".all41n14lla"
NODE_FOLDERS = ("concepts", "patterns", "episodes", "constraints")


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
    path = path.expanduser().resolve()
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
    console.print(f"[green]✓ Vault initialized at {path}[/green]")


@app.command()
def serve() -> None:
    """Run the MCP stdio server."""
    from all41n14lla.server import main

    main()


REQUIRED_DEPS = ("mcp", "typer", "yaml", "frontmatter", "watchdog", "rich")


@app.command()
def doctor() -> None:
    """Check environment + vault health."""
    from importlib.util import find_spec

    console.print(f"[bold]all41n14lla[/bold] v{__version__}")
    console.print(f"Python: {sys.version.split()[0]}")

    for mod in REQUIRED_DEPS:
        if find_spec(mod) is not None:
            console.print(f"[green]✓[/green] {mod}")
        else:
            console.print(f"[red]✗[/red] {mod} — missing")

    vault = DEFAULT_VAULT
    if vault.exists():
        console.print(f"[green]✓[/green] vault: {vault}")
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
) -> None:
    """Write a new memory. (Stub — full impl in v0.1.0.)"""
    console.print(f"[yellow]STUB[/yellow]: remember {node_type} — coming in v0.1.0")


@app.command()
def recall(
    query: str,
    node_type: str = typer.Option(None, "--type", help="Filter by type"),
    limit: int = typer.Option(10, "--limit", help="Max results"),
) -> None:
    """Search memories. (Stub.)"""
    console.print(f"[yellow]STUB[/yellow]: recall '{query}' — coming in v0.1.0")


@app.command()
def forget(node_id: str, confirm: bool = typer.Option(False, "--confirm")) -> None:
    """Delete a memory by id. (Stub.)"""
    console.print(f"[yellow]STUB[/yellow]: forget {node_id} — coming in v0.1.0")


@app.command()
def inspect(query: str) -> None:
    """Show nodes, edges, neighbors. (Stub.)"""
    console.print(f"[yellow]STUB[/yellow]: inspect '{query}' — coming in v0.1.0")


@app.command()
def consolidate() -> None:
    """Promote patterns from episodes + apply decay."""
    console.print("[yellow]Pattern promotion coming in v0.2.0[/yellow]")


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"all41n14lla {__version__}")


if __name__ == "__main__":
    app()
