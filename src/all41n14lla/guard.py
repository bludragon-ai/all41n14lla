"""Model-agnostic repetition detection for streaming text output."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

_COMPLETE_SEGMENT = re.compile(r".*?(?:\n|(?<!\d)[.!?](?:\s+|$))", re.DOTALL)
_LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[A-Za-z][.)])\s+")
_WORD = re.compile(r"[\w']+")


@dataclass(frozen=True)
class RepetitionMatch:
    """Observable details about the segment that caused a stream cutoff."""

    position: int
    similarity: float
    repeated_segment: str
    prior_segment: str


class RepetitionGuard:
    """Yield a text stream until a new segment substantially repeats prior output."""

    def __init__(
        self,
        threshold: float = 0.82,
        window_chars: int = 150,
        minimum_segment_chars: int = 12,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if window_chars < 1:
            raise ValueError("window_chars must be positive")
        if minimum_segment_chars < 1:
            raise ValueError("minimum_segment_chars must be positive")

        self.threshold = threshold
        self.window_chars = window_chars
        self.minimum_segment_chars = minimum_segment_chars
        self.loop_detected = False
        self.match: RepetitionMatch | None = None
        self.output = ""
        self._history: list[tuple[str, str]] = []

    def feed(self, chunks: Iterable[str]) -> Iterator[str]:
        """Yield safe text pieces and stop before the first repeated segment."""
        self.loop_detected = False
        self.match = None
        self.output = ""
        self._history = []
        pending = ""

        for chunk in chunks:
            if not isinstance(chunk, str):
                raise TypeError("all chunks must be strings")
            pending += chunk
            pieces, pending = _complete_segments(pending)
            for piece in pieces:
                if self._detect(piece):
                    return
                self.output += piece
                yield piece

        if pending:
            if self._detect(pending):
                return
            self.output += pending
            yield pending

    def _detect(self, segment: str) -> bool:
        normalized = _normalize(segment)
        if len(normalized) < self.minimum_segment_chars:
            return False

        best_ratio = 0.0
        best_prior = ""
        for prior_original, prior_normalized in self._history:
            ratio = _similarity(prior_normalized, normalized, self.window_chars)
            if ratio > best_ratio:
                best_ratio = ratio
                best_prior = prior_original

        self._history.append((segment, normalized[-self.window_chars :]))
        if best_ratio < self.threshold:
            return False

        self.loop_detected = True
        self.match = RepetitionMatch(
            position=len(self.output),
            similarity=best_ratio,
            repeated_segment=segment.strip(),
            prior_segment=best_prior.strip(),
        )
        logger.warning(
            "Repetition guard stopped output at character %d (similarity %.3f): %r repeated %r",
            self.match.position,
            self.match.similarity,
            self.match.repeated_segment,
            self.match.prior_segment,
        )
        return True

    def result(self) -> dict:
        """Return JSON-serializable guard state for CLI and MCP integrations."""
        return {
            "text": self.output,
            "loop_detected": self.loop_detected,
            "match": asdict(self.match) if self.match else None,
        }


def guard_stream(
    chunks: Iterable[str],
    *,
    threshold: float = 0.82,
    window_chars: int = 150,
) -> Iterator[str]:
    """Convenience wrapper yielding guarded chunks from any text iterator."""
    return RepetitionGuard(threshold=threshold, window_chars=window_chars).feed(chunks)


def guard_text(
    text: str,
    *,
    threshold: float = 0.82,
    window_chars: int = 150,
) -> tuple[str, bool]:
    """Guard complete text while exercising the same streaming implementation."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    guard = RepetitionGuard(threshold=threshold, window_chars=window_chars)
    output = "".join(guard.feed([text]))
    return output, guard.loop_detected


def _complete_segments(text: str) -> tuple[list[str], str]:
    matches = list(_COMPLETE_SEGMENT.finditer(text))
    pieces = [match.group() for match in matches if match.group()]
    consumed = matches[-1].end() if matches else 0
    return pieces, text[consumed:]


def _normalize(segment: str) -> str:
    without_prefix = _LIST_PREFIX.sub("", segment.strip().lower())
    return " ".join(_WORD.findall(without_prefix))


def _similarity(left: str, right: str, window_chars: int) -> float:
    left = left[-window_chars:]
    right = right[-window_chars:]
    sequence_ratio = SequenceMatcher(None, left, right, autojunk=False).ratio()
    left_words = set(_WORD.findall(left))
    right_words = set(_WORD.findall(right))
    overlap = len(left_words & right_words) / max(len(left_words), len(right_words), 1)
    return max(sequence_ratio, overlap)
