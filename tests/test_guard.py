import logging
from pathlib import Path

from all41n14lla.guard import RepetitionGuard, guard_text

FIXTURE = Path(__file__).parent / "fixtures" / "ornith-1.5-9b-near-duplicate-list.txt"


def test_ornith_near_duplicate_list_fixture_is_cut(caplog) -> None:
    text = FIXTURE.read_text()
    guard = RepetitionGuard()

    with caplog.at_level(logging.WARNING):
        output = "".join(guard.feed(_small_chunks(text, 17)))

    assert guard.loop_detected
    assert guard.match is not None
    assert guard.match.repeated_segment == "1. The Daily Grind"
    assert "Let me think of fresh names" in output
    assert output.count("The Daily Grind") == 1
    assert "Repetition guard stopped output" in caplog.text


def test_genuinely_non_repetitive_long_response_is_not_cut() -> None:
    text = " ".join(
        f"Section {index} describes a distinct event involving subject {index * 17} in place {index * 31}."
        for index in range(1, 33)
    )
    output, detected = guard_text(text)
    assert not detected
    assert output == text


def test_legitimate_numbered_structure_is_not_cut() -> None:
    lines = [
        "1. Sunrise Roasters serves single-origin pour-overs from a converted garage.",
        "2. Marisol's Cafe specializes in Cuban espresso and pastelitos.",
        "3. The Tinker's Cup roasts its own beans on-site every Tuesday.",
        "4. Blackbird Coffee runs a rotating guest-roaster program each month.",
        "5. Harbor Grounds overlooks the pier and only opens at dawn.",
        "6. Copper Kettle Coffee focuses on siphon brewing demonstrations.",
        "7. The Quiet Bean is a no-wifi, conversation-only coffeehouse.",
        "8. Nomad Roasters sources exclusively from women-owned farms.",
    ]
    text = "\n".join(lines) + "\n"
    output, detected = guard_text(text)
    assert not detected
    assert output == text


def test_immediate_short_exact_repeat_is_cut() -> None:
    repeated = "This short sentence repeats immediately. "
    guard = RepetitionGuard(window_chars=40)
    output = "".join(guard.feed([repeated, repeated]))
    assert guard.loop_detected
    assert output == repeated


def _small_chunks(text: str, size: int) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]
