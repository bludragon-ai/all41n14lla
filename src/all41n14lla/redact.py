"""PII redaction for report excerpts — single source of truth.

Defense-in-depth: even a forced `git add -f` of a benchmark report must not
publish emails, phones, or long digit runs (cards/accounts). Lives in the
package so the regression tests in tests/ can import it directly.
"""
from __future__ import annotations

import re

# Long digit runs (card/account numbers) — masked first so a phone-shaped
# number never swallows them.
_DIGIT_RUN_RE = re.compile(r"\d{10,}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Phone-ish: US (415) 555-0132 / 415-555-0132, or +country international.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}|\+\d{1,3}[\d\s.\-]{6,}\d)(?!\d)"
)


def redact(text: str) -> str:
    """Scrub high-signal PII classes from an excerpt (defense-in-depth)."""
    text = _DIGIT_RUN_RE.sub("[digits]", text)
    text = _EMAIL_RE.sub("[email]", text)
    return _PHONE_RE.sub("[phone]", text)
