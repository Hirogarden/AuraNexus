import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from typing import List, Dict


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

    def add_card(self, card: StoryCard) -> None:
        """Registers a new lore chunk or memory profile into the active book context."""
        self.cards[card.id] = card

    def scan_and_retrieve(
        self,
        context_text: str,
        mode: str = "storyteller",
        max_tokens: int = 2048,
    ) -> List[StoryCard]:
        """
        Scans recent conversation or narrative prose blocks, finds all matching cards,
        and returns them sorted by priority to prevent context bloating.
        """
        triggered_cards: List[StoryCard] = []
        
        allowed_modes = {"shared", mode}
        for card in self.cards.values():
            if card.mode not in allowed_modes:
                continue
            if card.matches(context_text):
                triggered_cards.append(card)
                
        # Sort by priority value descending (lower number = higher importance or vice versa depending on style)
        # We will treat higher priority numbers as more critical context anchors
        triggered_cards.sort(key=lambda x: x.priority, reverse=True)

        if max_tokens <= 0:
            return []

        budget = max_tokens
        selected_cards: List[StoryCard] = []
        for card in triggered_cards:
            estimated_tokens = max(1, len(card.content) // 4)
            if estimated_tokens <= budget:
                selected_cards.append(card)
                budget -= estimated_tokens

        return selected_cards

    def format_context_block(self, active_cards: List[StoryCard]) -> str:
        """Translates a collection of active cards into a clean, unified block for LLM parsing."""
        if not active_cards:
            return ""
            
        block_lines = ["[Lore & Context Memories Active]:"]
        for card in active_cards:
            block_lines.append(f"--- ({card.category.upper()}): {card.id} ---")
            block_lines.append(card.content.strip())
            
        return "\n".join(block_lines) + "\n"