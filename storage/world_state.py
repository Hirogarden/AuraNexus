import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Fact:
    key: str
    value: str
    source: str = "user"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    permanent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "created_at": self.created_at,
            "permanent": self.permanent,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Fact":
        return cls(
            key=str(payload["key"]),
            value=str(payload["value"]),
            source=str(payload.get("source", "user")),
            created_at=str(payload.get("created_at", datetime.now().isoformat())),
            permanent=bool(payload.get("permanent", False)),
        )


class WorldState:
    """Persistent key-value store for absolute facts that prompts must not contradict."""

    def __init__(self, data_path: str | Path = "world_state.json") -> None:
        self.data_path = Path(data_path)
        self._facts: Dict[str, Fact] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            return

        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Invalid world state file: top-level payload must be an object.")

        self._facts = {key: Fact.from_dict(value) for key, value in raw.items()}

    def _save(self) -> None:
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {key: fact.to_dict() for key, fact in self._facts.items()}
        self.data_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def assert_fact(
        self,
        key: str,
        value: str,
        source: str = "user",
        permanent: bool = False,
    ) -> None:
        normalized_key = str(key).strip()
        normalized_value = str(value).strip()
        if not normalized_key:
            raise ValueError("Fact key must be a non-empty string.")
        if not normalized_value:
            raise ValueError("Fact value must be a non-empty string.")

        existing = self._facts.get(normalized_key)
        if existing is not None and existing.permanent and source != "system":
            return

        self._facts[normalized_key] = Fact(
            key=normalized_key,
            value=normalized_value,
            source=str(source).strip() or "user",
            permanent=permanent,
        )
        self._save()

    def retract_fact(self, key: str) -> bool:
        normalized_key = str(key).strip()
        fact = self._facts.get(normalized_key)
        if fact is None or fact.permanent:
            return False
        del self._facts[normalized_key]
        self._save()
        return True

    def get(self, key: str, default: str = "") -> str:
        fact = self._facts.get(str(key).strip())
        return fact.value if fact else default

    def all_facts(self) -> List[Fact]:
        return list(self._facts.values())

    def as_prompt_block(self) -> str:
        if not self._facts:
            return ""

        system_facts = [fact for fact in self._facts.values() if fact.source == "system"]
        user_facts = [fact for fact in self._facts.values() if fact.source == "user"]
        other_facts = [
            fact for fact in self._facts.values() if fact.source not in {"system", "user"}
        ]

        lines = ["[Absolute facts - do not contradict these]"]
        for fact in system_facts + user_facts + other_facts:
            lines.append(f"- {fact.key}: {fact.value}")
        return "\n".join(lines)
