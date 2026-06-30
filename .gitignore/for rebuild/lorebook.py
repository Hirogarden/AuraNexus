"""
Lorebook — multiple-persona world-info system for AuraNexus.

Key concepts
------------
StoryCard
    A world-info entry.  When keywords appear in a user/narrator turn the
    card's content is injected into the system prompt, giving the LLM
    persistent context (character backstories, locations, rules, etc.).
    Cards can be global (available to all personas) or bound to a specific
    persona.

Persona
    A named AI character.  Each persona has a description, a list of
    persona-specific StoryCards, and an InnerSelf that tracks hidden
    internal state (mood, thoughts, goals).  Only one persona is "active"
    at a time; switching personas changes what cards and inner-self text
    are injected.

InnerSelf
    A persona's private internal state.  The LLM is told about this in the
    system prompt as a hidden-thoughts block so it can shape responses
    accordingly without necessarily saying those things out loud.

Auto-card creation
    When `auto_card_creation_enabled` is True the host code may call
    `auto_create_card()` to mint a new StoryCard from context (e.g. after
    detecting a recurring character name).

Forced cards
    Call `force_card()` to push a temporary card that will be included in
    the next prompt build regardless of keywords, then automatically
    removed.

Usage
-----
    lb = Lorebook(data_dir=Path("~/.local/share/auranexus/nexus_data"))
    lb.set_active_persona(persona_id)
    world_block = lb.build_world_info_block(user_text)
    inner_block  = lb.build_inner_self_block()
    lb.update_inner_self_after_turn("User mentioned their dog Rex.")
    lb.save()
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from auranexus.engine.atomic_io import _atomic_write_text


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StoryCard:
    """A single world-info entry."""
    card_id: str
    name: str
    content: str
    keywords: list[str]
    is_constant: bool        # inject regardless of keyword match
    priority: int            # higher = injected first when budget is tight
    persona_id: Optional[str]  # None = global; str = bound to this persona
    auto_generated: bool
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def matches(self, text: str) -> bool:
        """Return True if any keyword appears (case-insensitive) in text."""
        if self.is_constant:
            return True
        lower = text.lower()
        return any(kw.lower() in lower for kw in self.keywords if kw.strip())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StoryCard":
        return cls(**d)


@dataclass
class InnerSelf:
    """
    A persona's hidden internal state.

    This is injected into the system prompt as a private block so the LLM
    can shape responses around the character's private thoughts and goals
    without necessarily surfacing them directly.
    """
    current_mood: str = "neutral"
    hidden_thoughts: list[str] = field(default_factory=list)
    active_goals: list[str] = field(default_factory=list)
    relationship_with_user: str = ""
    personality_notes: str = ""

    _MAX_THOUGHTS: int = field(default=5, init=False, repr=False, compare=False)

    def add_thought(self, thought: str) -> None:
        """Append a thought; trim oldest when over limit."""
        self.hidden_thoughts.append(thought)
        if len(self.hidden_thoughts) > self._MAX_THOUGHTS:
            self.hidden_thoughts = self.hidden_thoughts[-self._MAX_THOUGHTS:]

    def as_prompt_block(self, persona_name: str) -> str:
        """
        Build the hidden-thoughts section that is injected into the system
        prompt just before the user turn.

        The block is framed as private internal state — the character knows
        these things but does not necessarily say them aloud.
        """
        lines = [
            f"[{persona_name}'s inner world — private, not spoken aloud]",
            f"Current mood: {self.current_mood}",
        ]
        if self.hidden_thoughts:
            lines.append("Hidden thoughts:")
            for t in self.hidden_thoughts:
                lines.append(f"  • {t}")
        if self.active_goals:
            lines.append("Current goals:")
            for g in self.active_goals:
                lines.append(f"  • {g}")
        if self.relationship_with_user:
            lines.append(f"Relationship notes: {self.relationship_with_user}")
        if self.personality_notes:
            lines.append(f"Personality: {self.personality_notes}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "current_mood": self.current_mood,
            "hidden_thoughts": list(self.hidden_thoughts),
            "active_goals": list(self.active_goals),
            "relationship_with_user": self.relationship_with_user,
            "personality_notes": self.personality_notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InnerSelf":
        obj = cls()
        obj.current_mood = d.get("current_mood", "neutral")
        obj.hidden_thoughts = list(d.get("hidden_thoughts", []))
        obj.active_goals = list(d.get("active_goals", []))
        obj.relationship_with_user = d.get("relationship_with_user", "")
        obj.personality_notes = d.get("personality_notes", "")
        return obj


@dataclass
class Persona:
    """A named AI character with their own story cards and inner self."""
    persona_id: str
    name: str
    description: str
    story_cards: list[StoryCard] = field(default_factory=list)
    inner_self: InnerSelf = field(default_factory=InnerSelf)
    is_active: bool = False
    # Presence status: "active" | "away" | "dead"
    status: str = "active"
    # Demographic profile for voice auto-assignment
    gender: str = ""
    age_range: str = ""        # e.g. "young", "middle-aged", "elderly"
    profession: str = ""       # e.g. "warrior", "mage", "merchant"
    # TTS tier: "piper" | "coqui" | "elevenlabs" | "espeak"
    tts_engine: str = "piper"
    # Per-persona TTS voice ID (engine-specific)
    voice_id: Optional[str] = None
    # Feature #14 placeholder — reserved for per-persona VRM/Live2D avatar
    avatar_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "description": self.description,
            "story_cards": [c.to_dict() for c in self.story_cards],
            "inner_self": self.inner_self.to_dict(),
            "is_active": self.is_active,
            "status": self.status,
            "gender": self.gender,
            "age_range": self.age_range,
            "profession": self.profession,
            "tts_engine": self.tts_engine,
            "voice_id": self.voice_id,
            "avatar_path": self.avatar_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        cards = [StoryCard.from_dict(c) for c in d.get("story_cards", [])]
        inner = InnerSelf.from_dict(d.get("inner_self", {}))
        return cls(
            persona_id=d["persona_id"],
            name=d["name"],
            description=d.get("description", ""),
            story_cards=cards,
            inner_self=inner,
            is_active=d.get("is_active", False),
            status=d.get("status", "active"),
            gender=d.get("gender", ""),
            age_range=d.get("age_range", ""),
            profession=d.get("profession", ""),
            tts_engine=d.get("tts_engine", "piper"),
            voice_id=d.get("voice_id"),
            avatar_path=d.get("avatar_path"),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )


# ---------------------------------------------------------------------------
# Lorebook
# ---------------------------------------------------------------------------

class Lorebook:
    """
    Container for all personas and global world-info cards.

    Persisted as ``<data_dir>/lorebook.json``.
    """

    SAVE_FILE = "lorebook.json"

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._save_path = data_dir / self.SAVE_FILE

        self.personas: list[Persona] = []
        self.global_cards: list[StoryCard] = []
        self.auto_card_creation_enabled: bool = False

        # Cards generated by proc-gen awaiting user review; NOT persisted.
        self.pending_cards: list[StoryCard] = []

        # Temporary cards pushed via force_card(); flushed after one prompt.
        self._forced_cards: list[StoryCard] = []

        self._load()

    # ------------------------------------------------------------------
    # Active persona
    # ------------------------------------------------------------------

    def active_persona(self) -> Optional[Persona]:
        """Return the currently active persona, or None."""
        for p in self.personas:
            if p.is_active:
                return p
        return None

    def set_active_persona(self, persona_id: Optional[str]) -> None:
        """Activate one persona by ID; deactivate all others.

        Pass ``None`` to deactivate all (use global settings instead).
        """
        for p in self.personas:
            p.is_active = p.persona_id == persona_id

    def add_persona(
        self,
        name: str,
        description: str = "",
        *,
        activate: bool = False,
    ) -> Persona:
        """Create and register a new persona; return it."""
        persona = Persona(
            persona_id=str(uuid.uuid4()),
            name=name,
            description=description,
        )
        self.personas.append(persona)
        if activate:
            self.set_active_persona(persona.persona_id)
        return persona

    def remove_persona(self, persona_id: str) -> None:
        """Remove a persona and all its cards."""
        self.personas = [p for p in self.personas if p.persona_id != persona_id]

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        for p in self.personas:
            if p.persona_id == persona_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Story-card management
    # ------------------------------------------------------------------

    def add_global_card(
        self,
        name: str,
        content: str,
        keywords: list[str],
        is_constant: bool = False,
        priority: int = 0,
    ) -> StoryCard:
        """Create and register a global (all-persona) card."""
        card = StoryCard(
            card_id=str(uuid.uuid4()),
            name=name,
            content=content,
            keywords=keywords,
            is_constant=is_constant,
            priority=priority,
            persona_id=None,
            auto_generated=False,
        )
        self.global_cards.append(card)
        return card

    def add_persona_card(
        self,
        persona_id: str,
        name: str,
        content: str,
        keywords: list[str],
        is_constant: bool = False,
        priority: int = 0,
    ) -> Optional[StoryCard]:
        """Add a story card to a specific persona.  Returns None if not found."""
        persona = self.get_persona(persona_id)
        if persona is None:
            return None
        card = StoryCard(
            card_id=str(uuid.uuid4()),
            name=name,
            content=content,
            keywords=keywords,
            is_constant=is_constant,
            priority=priority,
            persona_id=persona_id,
            auto_generated=False,
        )
        persona.story_cards.append(card)
        return card

    def remove_card(self, card_id: str) -> None:
        """Remove a card from global cards or from whichever persona owns it."""
        self.global_cards = [c for c in self.global_cards if c.card_id != card_id]
        for p in self.personas:
            p.story_cards = [c for c in p.story_cards if c.card_id != card_id]

    # ------------------------------------------------------------------
    # Pending-card review (proc-gen cards awaiting user approval)
    # ------------------------------------------------------------------

    def queue_pending_card(self, card: StoryCard) -> None:
        """Add a proc-gen card to the pending review queue."""
        self.pending_cards.append(card)

    def approve_pending(self, card_id: str) -> bool:
        """Move a pending card into the lorebook.  Returns True if found."""
        for i, card in enumerate(self.pending_cards):
            if card.card_id == card_id:
                self.pending_cards.pop(i)
                if card.persona_id is not None:
                    persona = self.get_persona(card.persona_id)
                    if persona is not None:
                        persona.story_cards.append(card)
                        self.save()
                        return True
                self.global_cards.append(card)
                self.save()
                return True
        return False

    def reject_pending(self, card_id: str) -> bool:
        """Discard a pending card.  Returns True if found."""
        for i, card in enumerate(self.pending_cards):
            if card.card_id == card_id:
                self.pending_cards.pop(i)
                return True
        return False

    # ------------------------------------------------------------------
    # Auto-card creation
    # ------------------------------------------------------------------

    def auto_create_card(
        self,
        name: str,
        content: str,
        keywords: list[str],
        persona_id: Optional[str] = None,
        priority: int = 1,
    ) -> StoryCard:
        """
        Automatically generate a new StoryCard from context.

        The host calls this when ``auto_card_creation_enabled`` is True and
        a notable entity / concept has been detected in the conversation.

        If ``persona_id`` is given the card is bound to that persona;
        otherwise it is added to the global pool.
        """
        card = StoryCard(
            card_id=str(uuid.uuid4()),
            name=name,
            content=content,
            keywords=keywords,
            is_constant=False,
            priority=priority,
            persona_id=persona_id,
            auto_generated=True,
        )
        if persona_id is not None:
            persona = self.get_persona(persona_id)
            if persona is not None:
                persona.story_cards.append(card)
                return card
        self.global_cards.append(card)
        return card

    # ------------------------------------------------------------------
    # Forced cards (injected in the very next prompt, then cleared)
    # ------------------------------------------------------------------

    def force_card(self, content: str, name: str = "Forced", keywords: list[str] | None = None) -> StoryCard:
        """
        Push a temporary card to be injected in the next prompt regardless
        of keyword matching.  Cleared when ``flush_forced_cards()`` is called.
        """
        card = StoryCard(
            card_id=str(uuid.uuid4()),
            name=name,
            content=content,
            keywords=keywords or [],
            is_constant=True,
            priority=100,      # highest priority
            persona_id=None,
            auto_generated=True,
        )
        self._forced_cards.append(card)
        return card

    def flush_forced_cards(self) -> list[StoryCard]:
        """Return and clear the list of forced cards."""
        cards, self._forced_cards = self._forced_cards, []
        return cards

    # ------------------------------------------------------------------
    # Prompt injection
    # ------------------------------------------------------------------

    def get_triggered_cards(self, text: str) -> list[StoryCard]:
        """
        Return all cards that should be injected given ``text``.

        Includes:
        - forced cards (temporary, one-shot)
        - global cards whose keywords match *or* that are constant
        - active persona's cards whose keywords match *or* that are constant
        Sorted by priority (descending) so highest-priority cards come first.
        """
        triggered: list[StoryCard] = []

        # Forced one-shots are always included regardless of text
        triggered.extend(self._forced_cards)

        # Global cards
        for card in self.global_cards:
            if card.matches(text):
                triggered.append(card)

        # Active persona's own cards
        persona = self.active_persona()
        if persona is not None:
            for card in persona.story_cards:
                if card.matches(text):
                    triggered.append(card)

        # Deduplicate by card_id while preserving order
        seen: set[str] = set()
        unique: list[StoryCard] = []
        for c in triggered:
            if c.card_id not in seen:
                seen.add(c.card_id)
                unique.append(c)

        return sorted(unique, key=lambda c: c.priority, reverse=True)

    def build_world_info_block(self, text: str) -> str:
        """
        Build the world-info injection block for a given prompt text.

        Returns an empty string if no cards are triggered.
        """
        cards = self.get_triggered_cards(text)
        if not cards:
            return ""
        lines = ["[World info]"]
        for card in cards:
            lines.append(f"### {card.name}")
            lines.append(card.content)
        return "\n".join(lines)

    def build_inner_self_block(self) -> str:
        """
        Build the inner-self injection block for the active persona.

        Returns an empty string when no persona is active.
        """
        persona = self.active_persona()
        if persona is None:
            return ""
        return persona.inner_self.as_prompt_block(persona.name)

    def build_persona_description_block(self) -> str:
        """
        Return the active persona's description as a short system block.

        Returns an empty string when no persona is active or when the
        description is blank.
        """
        persona = self.active_persona()
        if persona is None or not persona.description.strip():
            return ""
        return f"[{persona.name} — persona description]\n{persona.description.strip()}"

    # ------------------------------------------------------------------
    # Inner-self update
    # ------------------------------------------------------------------

    def update_inner_self_after_turn(
        self,
        thought: str,
        mood: Optional[str] = None,
        relationship_note: Optional[str] = None,
    ) -> None:
        """
        Record a new hidden thought (and optionally update mood / relationship
        notes) for the active persona after a completed conversation turn.

        No-op if no persona is active.
        """
        persona = self.active_persona()
        if persona is None:
            return
        persona.inner_self.add_thought(thought)
        if mood:
            persona.inner_self.current_mood = mood
        if relationship_note:
            persona.inner_self.relationship_with_user = relationship_note

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the lorebook to disk."""
        data = {
            "personas": [p.to_dict() for p in self.personas],
            "global_cards": [c.to_dict() for c in self.global_cards],
            "auto_card_creation_enabled": self.auto_card_creation_enabled,
        }
        _atomic_write_text(
            self._save_path,
            json.dumps(data, indent=2, ensure_ascii=False),
        )

    def _load(self) -> None:
        """Load from disk; silently initialize empty if file absent/corrupt."""
        if not self._save_path.exists():
            return
        try:
            data = json.loads(self._save_path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        self.personas = [Persona.from_dict(p) for p in data.get("personas", [])]
        self.global_cards = [StoryCard.from_dict(c) for c in data.get("global_cards", [])]
        self.auto_card_creation_enabled = data.get("auto_card_creation_enabled", False)
