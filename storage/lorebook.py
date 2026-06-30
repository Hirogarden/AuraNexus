import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set


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

    def matches(self, text: str) -> bool:
        """
        Scans the text using case-insensitive word boundary matching 
        to determine if this lore card should be active in context.
        """
        if not self.enabled:
            return False
            
        normalized_text = text.lower()
        for key in self.keys:
            # Enforce strict word boundaries so 'elf' doesn't accidentally trigger on 'myself'
            pattern = rf"\b{re.escape(key.lower())}\b"
            if re.search(pattern, normalized_text):
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

    def scan_and_retrieve(self, context_text: str, max_tokens: int = 2048) -> List[StoryCard]:
        """
        Scans recent conversation or narrative prose blocks, finds all matching cards,
        and returns them sorted by priority to prevent context bloating.
        """
        triggered_cards: List[StoryCard] = []
        
        for card in self.cards.values():
            if card.matches(context_text):
                triggered_cards.append(card)
                
        # Sort by priority value descending (lower number = higher importance or vice versa depending on style)
        # We will treat higher priority numbers as more critical context anchors
        triggered_cards.sort(key=lambda x: x.priority, reverse=True)
        return triggered_cards

    def format_context_block(self, active_cards: List[StoryCard]) -> str:
        """Translates a collection of active cards into a clean, unified block for LLM parsing."""
        if not active_cards:
            return ""
            
        block_lines = ["[Lore & Context Memories Active]:"]
        for card in active_cards:
            block_lines.append(f"--- ({card.category.upper()}): {card.id} ---")
            block_lines.append(card.content.strip())
            
        return "\n".join(block_lines) + "\n"