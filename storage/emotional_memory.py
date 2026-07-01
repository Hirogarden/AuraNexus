"""
EmotionalMemory — two optional systems for companion-mode context depth.

USER_MOOD_TRACKING:
    Records signals about how the user seems to be feeling over time.
    Aura uses this to adjust tone and notice patterns
    ("you've mentioned feeling overwhelmed a lot lately").

RELATIONSHIP_ARC:
    Tracks Aura's simulated familiarity with this user: how long they've
    talked, topics they've bonded over, warmth level. Aura grows more
    comfortable and personal the more they interact.

Both are stored in plain JSON under <base_path>/emotional/ so the user can
read, edit, or delete them at any time.

Ported and adapted from AuraNexus.old/auranexus/memory/emotional_memory.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Mood detection ─────────────────────────────────────────────────────────────

_MOOD_SIGNALS: Dict[str, List[str]] = {
    "happy":    ["happy", "great", "excited", "wonderful", "amazing", "joy",
                 "love", "fantastic", "thrilled", "glad", "delighted", "yay"],
    "stressed": ["stressed", "overwhelmed", "anxious", "worried", "panic",
                 "nervous", "tense", "pressure", "deadline", "too much"],
    "sad":      ["sad", "unhappy", "depressed", "down", "upset", "crying",
                 "cry", "miserable", "heartbroken", "grief", "lonely"],
    "tired":    ["tired", "exhausted", "sleepy", "fatigue", "worn out",
                 "drained", "no energy", "can't sleep", "insomnia"],
    "angry":    ["angry", "frustrated", "annoyed", "irritated", "furious",
                 "mad", "rage", "fed up", "hate this"],
    "curious":  ["curious", "wondering", "interested", "fascinated",
                 "intrigued", "want to know", "tell me more"],
    "playful":  ["lol", "haha", "funny", "joke", "laugh", "silly",
                 "play", "fun", "game"],
}

# How much a single detection shifts the running mood weight (0–1 scale)
_WEIGHT_STEP = 0.15
# How much the mood decays toward neutral each turn with no signal
_DECAY_RATE = 0.05


def _detect_mood_signals(text: str) -> List[str]:
    """Return list of mood labels detected in text (can be multiple)."""
    text_lower = text.lower()
    found = []
    for label, keywords in _MOOD_SIGNALS.items():
        if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in keywords):
            found.append(label)
    return found


# ── Topic detection ────────────────────────────────────────────────────────────

_TOPIC_MAP: Dict[str, List[str]] = {
    "coding":   ["code", "coding", "python", "javascript", "rust", "bug", "error",
                 "function", "class", "api", "library", "framework", "deploy", "git"],
    "gaming":   ["game", "gaming", "rpg", "fps", "quest", "dungeon", "playthrough",
                 "xbox", "playstation", "nintendo", "mod"],
    "music":    ["song", "music", "album", "band", "artist", "track", "playlist",
                 "guitar", "piano", "lyrics", "rap", "pop", "rock", "concert"],
    "movies":   ["movie", "film", "cinema", "show", "series", "episode", "watch",
                 "streaming", "actor", "director", "trailer"],
    "books":    ["book", "novel", "read", "author", "chapter", "fiction", "library"],
    "health":   ["health", "medical", "doctor", "exercise", "workout", "gym",
                 "diet", "sleep", "anxiety", "therapy", "wellness"],
    "science":  ["science", "physics", "chemistry", "biology", "space", "planet",
                 "research", "quantum", "technology", "climate"],
    "travel":   ["travel", "trip", "vacation", "hotel", "flight", "destination",
                 "country", "tour", "adventure"],
    "personal": [r"i am\b", r"i'm\b", r"i feel\b", "my life", "my family",
                 "my friend", "my job", "today i", "yesterday i"],
}

_DEFAULT_TOPIC = "general"


def _detect_topic(text: str) -> str:
    """Return a single topic label for text using keyword matching."""
    text_lower = text.lower()
    for topic, keywords in _TOPIC_MAP.items():
        for kw in keywords:
            pattern = kw if re.search(r"[\\()\[\]^$*+?{}|]", kw) else r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text_lower):
                return topic
    return _DEFAULT_TOPIC


# ── Persistence helpers ────────────────────────────────────────────────────────

def _load_json(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── EmotionalMemory ────────────────────────────────────────────────────────────

class EmotionalMemory:
    """
    Manages both emotional-memory systems.

    Parameters
    ----------
    base_path : str | Path
        Root directory. Emotional files go under <base_path>/emotional/.
    user_mood_tracking : bool
        Enable/disable tracking user mood signals.
    relationship_arc : bool
        Enable/disable Aura's simulated relationship arc.
    """

    def __init__(
        self,
        base_path: str | Path = ".",
        user_mood_tracking: bool = True,
        relationship_arc: bool = True,
    ) -> None:
        self.base_path = Path(base_path)
        self.emotional_path = self.base_path / "emotional"
        self.mood_file = self.emotional_path / "user_mood.json"
        self.arc_file = self.emotional_path / "relationship_arc.json"

        self.user_mood_tracking = user_mood_tracking
        self.relationship_arc = relationship_arc

        self._mood: Dict[str, Any] = _load_json(self.mood_file)
        self._arc: Dict[str, Any] = _load_json(self.arc_file)

        # Ensure defaults
        self._mood.setdefault("weights", {})
        self._mood.setdefault("history", [])
        self._mood.setdefault("last_seen", {})

        self._arc.setdefault("interaction_count", 0)
        self._arc.setdefault("total_messages", 0)
        self._arc.setdefault("first_met", None)
        self._arc.setdefault("last_talked", None)
        self._arc.setdefault("warmth", 0.0)
        self._arc.setdefault("topics_bonded", {})
        self._arc.setdefault("user_name", "")

        # Migrate legacy list format for topics_bonded
        if isinstance(self._arc.get("topics_bonded"), list):
            old_list = self._arc["topics_bonded"]
            migrated: Dict[str, int] = {}
            for entry in old_list:
                if isinstance(entry, str) and "(" in entry:
                    t, _, rest = entry.partition("(")
                    try:
                        migrated[t.strip()] = int(rest.rstrip(")"))
                    except ValueError:
                        migrated[entry] = 1
                elif isinstance(entry, str):
                    migrated[entry] = 1
            self._arc["topics_bonded"] = migrated

    # ── Public API ──────────────────────────────────────────────────────────

    def process_turn(
        self,
        user_message: str,
        assistant_response: str,
        user_name: str = "",
    ) -> None:
        """Update both memory systems from a single conversation turn."""
        now = datetime.now(tz=timezone.utc).isoformat()

        if self.user_mood_tracking:
            self._update_mood(user_message, now)

        if self.relationship_arc:
            self._update_arc(user_message, now, user_name)

    def get_context_block(self) -> str:
        """
        Return a short text block for injection into Aura's system prompt.
        Empty string when both systems are disabled or have nothing to report.
        """
        parts: List[str] = []

        if self.user_mood_tracking:
            mood_str = self._summarise_mood()
            if mood_str:
                parts.append(f"[User emotional context: {mood_str}]")

        if self.relationship_arc:
            arc_str = self._summarise_arc()
            if arc_str:
                parts.append(f"[Relationship context: {arc_str}]")

        return "\n".join(parts)

    def get_mood_summary(self) -> Dict[str, Any]:
        """Return the current mood weights dict (for UI display)."""
        return dict(self._mood.get("weights", {}))

    def get_arc_summary(self) -> Dict[str, Any]:
        """Return the arc stats (for UI display)."""
        return {
            "warmth": round(self._arc.get("warmth", 0.0), 2),
            "interaction_count": self._arc.get("total_messages", 0),
            "first_met": self._arc.get("first_met"),
            "last_talked": self._arc.get("last_talked"),
            "topics_bonded": self._arc.get("topics_bonded", {}),
        }

    def set_user_name(self, name: str) -> None:
        self._arc["user_name"] = name
        _save_json(self.arc_file, self._arc)

    def reload(self) -> None:
        """Re-read state from disk (e.g. after manual edits)."""
        self._mood = _load_json(self.mood_file)
        self._arc = _load_json(self.arc_file)
        self._mood.setdefault("weights", {})
        self._mood.setdefault("history", [])
        self._mood.setdefault("last_seen", {})
        self._arc.setdefault("interaction_count", 0)
        self._arc.setdefault("total_messages", 0)
        self._arc.setdefault("first_met", None)
        self._arc.setdefault("last_talked", None)
        self._arc.setdefault("warmth", 0.0)
        self._arc.setdefault("topics_bonded", {})
        self._arc.setdefault("user_name", "")

    # ── Internals: mood ────────────────────────────────────────────────────

    def _update_mood(self, text: str, now: str) -> None:
        signals = _detect_mood_signals(text)
        weights: Dict[str, float] = self._mood["weights"]

        if not signals:
            # Gentle decay toward neutral each turn
            for label in list(weights):
                weights[label] = max(0.0, weights[label] - _DECAY_RATE)
                if weights[label] == 0.0:
                    del weights[label]
        else:
            for label in signals:
                weights[label] = min(1.0, weights.get(label, 0.0) + _WEIGHT_STEP)
                self._mood["last_seen"][label] = now

            history: List[Dict[str, Any]] = self._mood["history"]
            history.append({"signals": signals, "ts": now, "text_snippet": text[:80]})
            if len(history) > 60:
                self._mood["history"] = history[-60:]

        _save_json(self.mood_file, self._mood)

    def _summarise_mood(self) -> str:
        weights: Dict[str, float] = self._mood.get("weights", {})
        dominant = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        active = [(label, w) for label, w in dominant if w >= 0.3]
        if not active:
            return ""
        top_label, top_weight = active[0]
        if top_weight >= 0.7:
            return f"strongly {top_label}"
        if top_weight >= 0.45:
            return f"somewhat {top_label}"
        if len(active) >= 2:
            return f"mixed ({top_label}, {active[1][0]})"
        return f"mildly {top_label}"

    # ── Internals: relationship arc ────────────────────────────────────────

    def _update_arc(self, text: str, now: str, user_name: str) -> None:
        arc = self._arc

        if user_name and not arc.get("user_name"):
            arc["user_name"] = user_name

        arc["total_messages"] = arc.get("total_messages", 0) + 1
        if arc.get("first_met") is None:
            arc["first_met"] = now
        arc["last_talked"] = now

        # Warmth grows slowly with interaction, caps at 1.0
        arc["warmth"] = min(1.0, arc.get("warmth", 0.0) + 0.005)

        # Track topics bonded over
        topic = _detect_topic(text)
        topics: Dict[str, int] = arc.setdefault("topics_bonded", {})
        topics[topic] = topics.get(topic, 0) + 1

        _save_json(self.arc_file, arc)

    def _summarise_arc(self) -> str:
        arc = self._arc
        warmth = arc.get("warmth", 0.0)
        total = arc.get("total_messages", 0)
        topics: Dict[str, int] = arc.get("topics_bonded", {})

        if total < 3:
            return ""

        warmth_label = "close" if warmth >= 0.7 else "familiar" if warmth >= 0.35 else "acquainted"
        top_topics = sorted(topics.items(), key=lambda kv: kv[1], reverse=True)[:2]
        topic_str = " and ".join(t for t, _ in top_topics if t != "general")

        parts = [f"{warmth_label} ({total} messages)"]
        if topic_str:
            parts.append(f"shared interests: {topic_str}")
        return ", ".join(parts)
