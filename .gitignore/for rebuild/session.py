"""
StorySession — holds all state for a single You'niverse story.

One session = one story world.  Multiple sessions can be saved and resumed.
The session is the source of truth for what the narrator prompt looks like.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from auranexus.engine.atomic_io import _atomic_write_text
from auranexus.engine.sanitize import sanitize_untrusted as _sanitize_untrusted

@dataclass
class StoryBeat:
    """One exchange in the story (player action → narrator response)."""
    player_action: str
    narrator_response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StorySession:
    """
    Everything needed to reconstruct the storytelling context.

    Fields
    ------
    title        : Short name shown in the session list.
    genre        : e.g. "Fantasy", "Sci-Fi", "Horror", "Slice of Life"
    tone         : e.g. "Dark & gritty", "Light-hearted", "Mysterious"
    setting      : One-paragraph world description provided by the player.
    player_name  : Character name the player chose.
    player_desc  : Brief character description (optional).
    narrator_name: What the narrator calls itself in-world (default = aura_name).
    beats        : Ordered list of story beats so far.
    created_at   : ISO timestamp.
    session_id   : Unique slug for file storage.
    """
    title:         str
    genre:         str
    tone:          str
    setting:       str
    player_name:   str
    player_desc:   str = ""
    narrator_name: str = "Aura"
    pov:           str = "second"   # "second" | "third"
    agency:        int = 2          # 1=AI never acts for player … 5=AI fully puppets
    beats:         list[StoryBeat] = field(default_factory=list)
    created_at:    str = field(default_factory=lambda: datetime.now().isoformat())
    session_id:    str = field(default_factory=lambda: datetime.now().strftime("story_%Y%m%d_%H%M%S"))
    last_corrupted_count: ClassVar[int] = 0

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_system_prompt(self) -> str:
        pov_instruction = (
            "Write in second person — address the player as 'you' "
            "(e.g. 'You step into the room...')."
            if self.pov == "second"
            else f"Write in third person — refer to the player as '{self.player_name}' "
            f"(e.g. '{self.player_name} steps into the room...')."
        )
        _agency_rules = {
            1: "NEVER write actions or dialogue for the player character. Only narrate the world around them.",
            2: "Avoid writing for the player character directly. You may describe very minor involuntary reactions (a blush, sharp breath) but never have them speak or act.",
            3: "Occasionally you may write a small reaction or movement for the player, but keep it subtle. Never put important words or decisions in their mouth.",
            4: "You may write for the player character moderately — small actions and brief reactions are fine. Avoid major decisions on their behalf.",
            5: "You may write freely for the player character as a full co-author, including their actions, speech, and decisions.",
        }
        agency_rule = _agency_rules.get(max(1, min(5, self.agency)), _agency_rules[2])

        return (
            f"You are a vivid and imaginative narrator for an interactive story.\n"
            f"Genre: {self.genre}. Tone: {self.tone}.\n"
            f"World: {self.setting}\n"
            f"Player character: {self.player_name}"
            + (f" — {self.player_desc}" if self.player_desc else "")
            + f"\n\nPOV: {pov_instruction}\n"
            f"Player agency: {agency_rule}\n\n"
            "Rules:\n"
            "- Write in flowing prose. Do NOT prefix responses with any name, "
            "label, or attribution — output only the story text itself.\n"
            "- Always use proper quotation marks (\u201c\u201d or \"\") for all spoken dialogue. "
            "Every line of speech a character speaks must be enclosed in quotes.\n"
            "- Keep each narration focused and vivid; end on an open moment that invites action.\n"
            "- Track what has already happened; maintain continuity.\n"
            "- Match the requested tone consistently."
        )

    def build_context_window(self, max_beats: int = 6) -> str:
        """Return the recent story history as a plain-text block for the prompt."""
        if not self.beats:
            return ""
        recent = self.beats[-max_beats:]
        lines = []
        for beat in recent:
            # Sanitize stored beat content when replaying — beats contain
            # historical player input and narrator responses, both of which
            # may have been stored before sanitization was applied.
            if beat.player_action:
                lines.append(f"[{self.player_name}]: {_sanitize_untrusted(beat.player_action)}")
            if beat.narrator_response:
                lines.append(_sanitize_untrusted(beat.narrator_response))
        return "\n".join(lines)

    def build_prompt(self, player_action: str, extra_system: str = "") -> str:
        """Full prompt for the next narrator response.

        Parameters
        ----------
        player_action : str
            The player's current action/input.
        extra_system : str, optional
            Additional text appended to the system prompt (e.g. story-script
            world info).  Empty string means no addition.
        """
        system = self.build_system_prompt()
        if extra_system:
            # extra_system comes from story scripts (user-loaded code); sanitize
            # before injecting into the system block.
            system = system + "\n\n" + _sanitize_untrusted(extra_system)
        parts = [f"System: {system}"]
        ctx = self.build_context_window()
        if ctx:
            parts.append(ctx)
        # Sanitize player_action — it is direct user input and must not
        # contain format tokens or role-header hijacks.
        parts.append(f"{self.player_name}: {_sanitize_untrusted(player_action)}")
        parts.append(f"{self.narrator_name}:")
        return "\n\n".join(parts)

    def add_beat(self, player_action: str, narrator_response: str) -> None:
        self.beats.append(StoryBeat(
            player_action=player_action,
            narrator_response=narrator_response,
        ))

    def rollback_last_beat(self) -> "StoryBeat | None":
        """Remove and return the last story beat.  Returns None if no beats exist."""
        if not self.beats:
            return None
        return self.beats.pop()

    def edit_beat(self, index: int, new_response: str) -> bool:
        """Replace the narrator_response of beat at *index*.  Returns False if out of range."""
        if index < 0 or index >= len(self.beats):
            return False
        self.beats[index].narrator_response = new_response
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _save_dir() -> Path:
        p = Path.home() / ".local" / "share" / "auranexus" / "stories"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save(self) -> Path:
        path = self._save_dir() / f"{self.session_id}.json"
        # Convert dataclass to dict, handling nested StoryBeat list
        d = asdict(self)
        _atomic_write_text(path, json.dumps(d, indent=2, ensure_ascii=False))
        return path

    @classmethod
    def load(cls, session_id: str) -> "StorySession":
        import logging
        path = cls._save_dir() / f"{session_id}.json"
        d = json.loads(path.read_text())
        beats = []
        for b in d.pop("beats", []):
            # P10: Validate beat tuple structure before unpacking
            if isinstance(b, dict) and "beats" in b and isinstance(b["beats"], (list, tuple)):
                if len(b["beats"]) >= 2:
                    beats.append(StoryBeat(**b))
                else:
                    logging.warning(f"Session {session_id}: skipping corrupted beat tuple with {len(b['beats'])} elements")
            else:
                try:
                    beats.append(StoryBeat(**b))
                except TypeError as exc:
                    logging.warning(f"Session {session_id}: skipping corrupted beat ({exc})")
        obj = cls(**d)
        obj.beats = beats
        return obj

    @classmethod
    def list_saved(cls) -> list[dict]:
        """Return [{session_id, title, genre, created_at}, ...] sorted newest-first.
        P35: Log and skip corrupted files; surface count to user.
        """
        import logging
        results = []
        skipped = 0
        for p in cls._save_dir().glob("*.json"):
            try:
                d = json.loads(p.read_text())
                results.append({
                    "session_id": d.get("session_id", p.stem),
                    "title":      d.get("title", "Untitled"),
                    "genre":      d.get("genre", ""),
                    "created_at": d.get("created_at", ""),
                })
            except (json.JSONDecodeError, OSError) as exc:
                # P35: Log and skip corrupted
                logging.warning(f"Skipped corrupted session file {p.name}: {exc}")
                skipped += 1
        if skipped > 0:
            logging.info(f"Skipped {skipped} corrupted session files during list")
        cls.last_corrupted_count = skipped
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    @classmethod
    def delete(cls, session_id: str) -> bool:
        """Delete a saved story by session_id.  Returns True if the file was found and removed."""
        path = cls._save_dir() / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
