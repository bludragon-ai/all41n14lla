"""Optional persona layer on top of a vault.

A vault works fine with no persona at all — this is an add-on, not a
requirement. `all41n14lla init --name/--address/--tone` writes PERSONA.md
into the vault; without those flags, `init` behaves exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class Persona:
    name: str
    address: str
    tone: str


def render_persona(persona: Persona) -> str:
    template = files("all41n14lla.templates").joinpath("PERSONA.md").read_text(encoding="utf-8")
    return template.format(name=persona.name, address=persona.address, tone=persona.tone)


def write_persona(vault: Path, persona: Persona) -> Path:
    """Write PERSONA.md into an existing vault. Caller ensures the vault exists."""
    path = vault / "PERSONA.md"
    path.write_text(render_persona(persona), encoding="utf-8")
    return path


def persona_text(vault: Path) -> str | None:
    """Return the vault's persona text, or None if no persona has been set."""
    path = vault / "PERSONA.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None
