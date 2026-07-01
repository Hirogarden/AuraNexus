import re
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import List, Dict, Iterable


@dataclass
class StoryCard:
    """
    Represents an isolated unit of world lore, character data, or assistant memory.
    Designed to trigger dynamically when specific keywords are matched in conversation or prose.
    """
    id: str
    keys: List[str]
    content: str
    category: str = "general"
    priority: int = 10
    enabled: bool = True
    mode: str = "shared"
    fuzzy_threshold: float = 0.88
    persona_id: str | None = None
    state_tags: List[str] = field(default_factory=list)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def _phrase_or_token_match(self, normalized_text: str, key: str) -> bool:
        key_norm = self._normalize(key)
        if not key_norm:
            return False

        if " " in key_norm:
            return key_norm in normalized_text

        pattern = rf"\b{re.escape(key_norm)}\b"
        return re.search(pattern, normalized_text) is not None

    def _fuzzy_match(self, normalized_text: str, key: str) -> bool:
        key_norm = self._normalize(key)
        if not key_norm:
            return False

        if len(key_norm) < 5:
            return False

        words = normalized_text.split()
        key_words = key_norm.split()
        window_size = max(1, len(key_words))

        if len(words) < window_size:
            return False

        for idx in range(0, len(words) - window_size + 1):
            window = " ".join(words[idx:idx + window_size])
            score = SequenceMatcher(None, window, key_norm).ratio()
            if score >= self.fuzzy_threshold:
                return True
        return False

    def matches(self, text: str) -> bool:
        """
        Scans the text using case-insensitive word boundary matching 
        to determine if this lore card should be active in context.
        """
        if not self.enabled:
            return False

        normalized_text = self._normalize(text)
        for key in self.keys:
            if self._phrase_or_token_match(normalized_text, key):
                return True
            if self._fuzzy_match(normalized_text, key):
                return True
        return False


class LorebookManager:
    """
    Manages collection, runtime activation, and context formatting of StoryCards.
    Allows AuraNexus to scale its knowledge base dynamically without context-window overflow.
    """
    
    def __init__(self):
        self.cards: Dict[str, StoryCard] = {}
        self.active_persona_id: str | None = None
        self.active_state_tags: set[str] = set()
        self._forced_card_ids: set[str] = set()

    def add_card(self, card: StoryCard) -> None:
        """Registers a new lore chunk or memory profile into the active book context."""
        self.cards[card.id] = card

    def remove_card(self, card_id: str) -> bool:
        if card_id not in self.cards:
            return False
        del self.cards[card_id]
        self._forced_card_ids.discard(card_id)
        return True

    def set_active_persona(self, persona_id: str | None) -> None:
        self.active_persona_id = persona_id.strip() if isinstance(persona_id, str) and persona_id.strip() else None

    def set_active_state_tags(self, state_tags: Iterable[str] | None) -> None:
        normalized: set[str] = set()
        if state_tags is not None:
            for tag in state_tags:
                tag_text = str(tag).strip().lower()
                if tag_text:
                    normalized.add(tag_text)
        self.active_state_tags = normalized

    def force_card(self, card_id: str) -> None:
        if card_id not in self.cards:
            raise KeyError(f"Unknown lore card '{card_id}'.")
        self._forced_card_ids.add(card_id)

    def clear_forced_cards(self) -> None:
        self._forced_card_ids.clear()

    def _card_matches_scope(
        self,
        card: StoryCard,
        mode: str,
        persona_id: str | None,
        state_tags: set[str],
    ) -> bool:
        if card.mode not in {"shared", mode}:
            return False

        if card.persona_id is not None and card.persona_id != persona_id:
            return False

        normalized_card_tags = {str(tag).strip().lower() for tag in card.state_tags if str(tag).strip()}
        if normalized_card_tags and not normalized_card_tags.intersection(state_tags):
            return False

        return True

    def scan_and_retrieve(
        self,
        context_text: str,
        mode: str = "storyteller",
        max_tokens: int = 2048,
        persona_id: str | None = None,
        state_tags: Iterable[str] | None = None,
    ) -> List[StoryCard]:
        """
        Scans recent conversation or narrative prose blocks, finds all matching cards,
        and returns them sorted by priority to prevent context bloating.
        """
        normalized_persona_id = persona_id if persona_id is not None else self.active_persona_id
        normalized_state_tags = set(self.active_state_tags)
        if state_tags is not None:
            normalized_state_tags = {
                str(tag).strip().lower() for tag in state_tags if str(tag).strip()
            }

        triggered_cards: List[StoryCard] = []
        for card in self.cards.values():
            if not self._card_matches_scope(card, mode, normalized_persona_id, normalized_state_tags):
                continue
            if card.id in self._forced_card_ids or card.matches(context_text):
                triggered_cards.append(card)
                
        triggered_cards.sort(
            key=lambda card: (card.id in self._forced_card_ids, card.priority),
            reverse=True,
        )

        if max_tokens <= 0:
            return []

        budget = max_tokens
        selected_cards: List[StoryCard] = []
        for card in triggered_cards:
            estimated_tokens = max(1, len(card.content) // 4)
            if estimated_tokens <= budget:
                selected_cards.append(card)
                budget -= estimated_tokens

        self.clear_forced_cards()
        return selected_cards

    def format_context_block(self, active_cards: List[StoryCard]) -> str:
        """Translates a collection of active cards into a clean, unified block for LLM parsing."""
        if not active_cards:
            return ""
            
        block_lines = ["[Lore & Context Memories Active]:"]
        for card in active_cards:
            scope_parts = [card.category.upper()]
            if card.persona_id:
                scope_parts.append(f"persona={card.persona_id}")
            if card.state_tags:
                scope_parts.append(f"states={','.join(card.state_tags)}")
            block_lines.append(f"--- ({' | '.join(scope_parts)}): {card.id} ---")
            block_lines.append(card.content.strip())
            
        return "\n".join(block_lines) + "\n"