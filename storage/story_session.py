import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class StoryBeat:
    player_action: str
    narrator_response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StorySession:
    title: str
    genre: str
    tone: str
    setting: str
    player_name: str
    player_desc: str = ""
    narrator_name: str = "Aura"
    beats: List[StoryBeat] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = field(default_factory=lambda: datetime.now().strftime("story_%Y%m%d_%H%M%S"))

    def build_system_prompt(self) -> str:
        player_clause = self.player_name
        if self.player_desc:
            player_clause = f"{player_clause} - {self.player_desc}"
        return (
            f"You are {self.narrator_name}, a vivid and imaginative narrator for an interactive story.\n"
            f"Genre: {self.genre}. Tone: {self.tone}.\n"
            f"World: {self.setting}\n"
            f"Player character: {player_clause}\n\n"
            "Rules:\n"
            "- Never take control of the player's character or make decisions for them.\n"
            "- Keep each narration focused and vivid; end on an open moment that invites action.\n"
            "- Track what has already happened; maintain continuity.\n"
            "- Match the requested tone consistently."
        )

    def build_context_window(self, max_beats: int = 6) -> str:
        if max_beats < 1 or not self.beats:
            return ""

        lines: List[str] = []
        for beat in self.beats[-max_beats:]:
            lines.append(f"{self.player_name}: {beat.player_action}")
            lines.append(f"{self.narrator_name}: {beat.narrator_response}")
        return "\n".join(lines)

    def build_prompt(self, player_action: str, extra_system: str = "") -> str:
        system_prompt = self.build_system_prompt()
        if extra_system.strip():
            system_prompt = f"{system_prompt}\n\n{extra_system.strip()}"

        sections = [f"System: {system_prompt}"]
        context = self.build_context_window()
        if context:
            sections.append(context)
        sections.append(f"{self.player_name}: {player_action}")
        sections.append(f"{self.narrator_name}:")
        return "\n\n".join(sections)

    def add_beat(self, player_action: str, narrator_response: str) -> None:
        self.beats.append(StoryBeat(player_action=player_action, narrator_response=narrator_response))

    def rollback_last_beat(self) -> StoryBeat | None:
        if not self.beats:
            return None
        return self.beats.pop()

    def edit_beat(self, index: int, new_response: str) -> bool:
        if index < 0 or index >= len(self.beats):
            return False
        self.beats[index].narrator_response = new_response
        return True

    def save(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, file_path: str | Path) -> "StorySession":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        beats = [StoryBeat(**beat) for beat in payload.pop("beats", [])]
        session = cls(**payload)
        session.beats = beats
        return session
