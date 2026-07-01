"""
ResponseTracker — suppresses repetitive openings, closings, and filler phrases.

After each completed response call ``record(response)``.
Before building the system prompt call ``as_prompt_block()`` and inject the
result near the end of the assembled prompt so the LLM sees it immediately
before it starts generating.

Ported and adapted from AuraNexus.old/auranexus/engine/response_tracker.py.
"""
from __future__ import annotations

import re
from collections import deque
from typing import Optional

# How many chars to capture from the start/end of each response
_SNIPPET_CHARS = 80

# How many past responses to look back
_HISTORY_SIZE = 6

# Minimum response length before we bother tracking it
_MIN_RESPONSE_LEN = 40

# Openers that are always banned regardless of history.
# LLMs reach for these automatically; hard-coding avoids the cold-start
# problem (no history yet on the first few turns).
_BANNED_OPENERS: tuple[str, ...] = (
    "Of course!",
    "Certainly!",
    "Absolutely!",
    "Sure thing!",
    "Great question",
    "That's a great",
    "I understand that",
    "I understand your",
    "As your AI",
    "As an AI",
    "As a language model",
    "I'm here to help",
    "I'd be happy to help",
    "I'd be delighted",
    "Allow me to",
)

# Closings that are always banned.
_BANNED_CLOSINGS: tuple[str, ...] = (
    "Let me know if you need anything",
    "Let me know if you have any",
    "Feel free to ask",
    "Hope that helps!",
    "Hope this helps!",
    "Is there anything else",
    "Is there anything I can",
    "Don't hesitate to ask",
)


def _first_sentence(text: str) -> str:
    """Return the first sentence or up to _SNIPPET_CHARS chars."""
    m = re.search(r"[.!?](?:\s|$)", text)
    if m:
        return text[: m.end()].strip()
    return text[:_SNIPPET_CHARS].strip()


def _last_sentence(text: str) -> str:
    """Return the last sentence or the trailing _SNIPPET_CHARS chars."""
    matches = list(re.finditer(r"[.!?](?:\s|$)", text))
    if len(matches) >= 2:
        return text[matches[-2].end():].strip()
    return text[-_SNIPPET_CHARS:].strip()


class ResponseTracker:
    """Tracks recent response patterns to prevent repetitive phrasing."""

    def __init__(self, history_size: int = _HISTORY_SIZE) -> None:
        self._openings: deque[str] = deque(maxlen=history_size)
        self._closings: deque[str] = deque(maxlen=history_size)

    def record(self, response: str) -> None:
        """Feed a completed response into the tracker."""
        text = response.strip()
        if len(text) < _MIN_RESPONSE_LEN:
            return
        opening = _first_sentence(text)
        closing = _last_sentence(text)
        if opening:
            self._openings.append(opening)
        if closing and closing != opening and len(closing) > 15:
            self._closings.append(closing)

    def reset(self) -> None:
        """Clear all tracked history (e.g. on new session)."""
        self._openings.clear()
        self._closings.clear()

    def as_prompt_block(self) -> str:
        """
        Return a compact instruction block to inject into the prompt.

        Always non-empty (banned openers list is always present) so the LLM
        gets anti-repetition cues from turn one.
        """
        lines: list[str] = [
            "[Style: vary your phrasing — never open or close with these:]",
        ]

        for phrase in _BANNED_OPENERS:
            lines.append(f'• Never open with: "{phrase}…"')

        for phrase in _BANNED_CLOSINGS:
            lines.append(f'• Never close with: "{phrase}…"')

        if self._openings:
            lines.append("[Recent openings — do not repeat:]")
            for opening in self._openings:
                lines.append(f'• "{opening}"')

        if self._closings:
            lines.append("[Recent closings — do not repeat:]")
            for closing in self._closings:
                lines.append(f'• "{closing}"')

        return "\n".join(lines)
