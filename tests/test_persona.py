from pathlib import Path

from all41n14lla.persona import Persona, persona_text, write_persona


def test_write_persona_renders_into_existing_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    path = write_persona(vault, Persona("Aster", "Captain", "warm and direct"))

    assert path == vault / "PERSONA.md"
    text = path.read_text()
    assert "Persona: Aster" in text
    assert "Captain" in text
    assert "warm and direct" in text


def test_persona_text_returns_none_when_unset(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    assert persona_text(vault) is None


def test_persona_text_returns_written_content(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    write_persona(vault, Persona("Aster", "Captain", "direct"))

    text = persona_text(vault)

    assert text is not None
    assert "Aster" in text
