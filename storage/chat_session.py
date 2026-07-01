import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class ChatTurn:
    user_text: str
    assistant_text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ChatSession:
    session_id: str
    name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    turns: List[ChatTurn] = field(default_factory=list)

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self.turns.append(ChatTurn(user_text=user_text, assistant_text=assistant_text))

    def recent_turns(self, limit: int) -> List[ChatTurn]:
        if limit < 1:
            return []
        return self.turns[-limit:]

    def save(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, file_path: str | Path) -> "ChatSession":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        turns = [ChatTurn(**turn) for turn in payload.pop("turns", [])]
        session = cls(**payload)
        session.turns = turns
        return session
