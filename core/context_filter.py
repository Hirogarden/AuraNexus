"""
Context Filter Matrix — mode-aware memory gate for AuraNexus.

Enforces strict data-pool boundaries between Companion and Storyteller pipelines.
No cross-contamination of emotional memory, story state, or world-facts is allowed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Memory Pool Definitions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SHARED (both modes)
  • General world knowledge from HiRAG nodes tagged "shared" or untagged
  • Objective reference facts pulled via vector similarity

COMPANION-ONLY (locked out of Storyteller)
  • HiRAG emotional memory index  (tag="emotional")
  • EmotionalMemory logs           (user_mood.json / relationship_arc.json)
  • Personal research memory nodes (tag="personal" or "research")

STORYTELLER-ONLY (locked out of Companion)
  • WorldState facts               (world_state.json)
  • Active StoryCards              (mode="storyteller" or mode="story")
  • Campaign / scenario memory     (tag="story", "campaign", "scenario", "lore")
  • Narrator prompt template context

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage (called from AuraRuntime._build_companion_prompt / _build_story_prompt):

    from core.context_filter import ContextFilter, MemoryMode

    cf = ContextFilter(mode=MemoryMode.COMPANION)
    nodes_for_prompt = cf.filter_hirag_nodes(all_nodes)
    emotional_ok     = cf.allows_emotional_memory()
    worldstate_ok    = cf.allows_world_state()
    lorecards_ok     = cf.filter_lore_cards(all_cards)
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ── Mode enum ──────────────────────────────────────────────────────────────────

class MemoryMode(str, Enum):
    COMPANION   = "companion"
    STORYTELLER = "storyteller"


# ── Tag sets that define each pool ────────────────────────────────────────────

# Tags that mark a node/card as belonging ONLY to the Companion pool
_COMPANION_ONLY_TAGS = frozenset({
    "emotional", "personal", "research", "mood", "relationship",
})

# Tags that mark a node/card as belonging ONLY to the Storyteller pool
_STORYTELLER_ONLY_TAGS = frozenset({
    "story", "storyteller", "campaign", "scenario", "lore",
    "world", "inventory", "party", "narrator", "rpg",
})


# ── ContextFilter ──────────────────────────────────────────────────────────────

class ContextFilter:
    """
    Stateless gate that decides what memory each pipeline is allowed to see.

    Instantiate once per prompt-build call with the current mode.
    All methods are deterministic and side-effect-free.
    """

    def __init__(self, mode: MemoryMode | str) -> None:
        if isinstance(mode, str):
            mode = MemoryMode(mode.lower())
        self.mode = mode

    # ------------------------------------------------------------------
    # Boolean gates (fast path for entire sub-systems)
    # ------------------------------------------------------------------

    def allows_emotional_memory(self) -> bool:
        """EmotionalMemory (mood logs, relationship arc) → companion only."""
        return self.mode == MemoryMode.COMPANION

    def allows_world_state(self) -> bool:
        """WorldState facts → storyteller only."""
        return self.mode == MemoryMode.STORYTELLER

    def allows_story_cards(self) -> bool:
        """StoryCards with mode='storyteller'|'story' → storyteller only."""
        return self.mode == MemoryMode.STORYTELLER

    # ------------------------------------------------------------------
    # HiRAG node filtering
    # ------------------------------------------------------------------

    def filter_hirag_nodes(
        self,
        nodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Return only the nodes visible to the current mode.

        A node is visible when:
          - Its tag set has no pool-specific tags (it is shared general knowledge), OR
          - Its tag set contains tags matching this mode's pool, but NOT the other.

        Nodes exclusively tagged for the other mode are silently dropped.
        """
        allowed: List[Dict[str, Any]] = []
        for node in nodes:
            tags = self._extract_node_tags(node)
            if self._node_is_allowed(tags):
                allowed.append(node)
        return allowed

    # ------------------------------------------------------------------
    # Lore-card filtering
    # ------------------------------------------------------------------

    def filter_lore_cards(self, cards: list) -> list:
        """
        Accept lore cards whose `mode` attribute is compatible with the
        current pipeline.

        card.mode values and visibility:
          "companion"   → companion only
          "storyteller" → storyteller only
          "story"       → storyteller only
          "shared"      → both
          (unset/other) → both (safe default)
        """
        allowed = []
        for card in cards:
            card_mode = (getattr(card, "mode", None) or "shared").lower()
            if card_mode in ("companion",):
                if self.mode == MemoryMode.COMPANION:
                    allowed.append(card)
            elif card_mode in ("storyteller", "story"):
                if self.mode == MemoryMode.STORYTELLER:
                    allowed.append(card)
            else:
                # "shared" or anything unrecognised → always visible
                allowed.append(card)
        return allowed

    # ------------------------------------------------------------------
    # Search-result filtering (used when querying the HiRAG store)
    # ------------------------------------------------------------------

    def filter_search_results(
        self,
        results: List[tuple],
    ) -> List[tuple]:
        """
        Filter (text, metadata, score) triples returned by
        LocalVectorStore.query_hierarchical().

        Drops results whose metadata tags belong exclusively to the other mode.
        """
        allowed = []
        for item in results:
            text, metadata, score = item[0], item[1], item[2]
            tags = self._extract_node_tags(metadata)
            if self._node_is_allowed(tags):
                allowed.append(item)
        return allowed

    # ------------------------------------------------------------------
    # Helper: assemble a "denied block" for the prompt (safety audit trail)
    # ------------------------------------------------------------------

    def denied_pools_note(self) -> str:
        """
        Returns a terse prompt annotation listing which pools are locked out.
        Injected into the system prompt so the model never accidentally
        references data it was not given.
        """
        if self.mode == MemoryMode.COMPANION:
            return (
                "[Context boundary — COMPANION mode: "
                "story world-state, StoryCards, and narrative campaign data "
                "are NOT available in this pipeline and must not be referenced.]"
            )
        return (
            "[Context boundary — STORYTELLER mode: "
            "personal emotional memory and research logs "
            "are NOT available in this pipeline and must not be referenced.]"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_node_tags(self, node: Dict[str, Any]) -> frozenset:
        """Pull tags from a node/metadata dict.  Handles list and string forms."""
        raw = node.get("tags") or node.get("tag") or node.get("category") or []
        if isinstance(raw, str):
            raw = [t.strip() for t in raw.replace(",", " ").split() if t.strip()]
        return frozenset(str(t).lower() for t in raw)

    def _node_is_allowed(self, tags: frozenset) -> bool:
        """Core visibility logic."""
        if self.mode == MemoryMode.COMPANION:
            # Block nodes exclusively tagged for the storyteller pool
            if tags & _STORYTELLER_ONLY_TAGS and not (tags & _COMPANION_ONLY_TAGS):
                return False
            return True
        else:  # STORYTELLER
            # Block nodes exclusively tagged for the companion pool
            if tags & _COMPANION_ONLY_TAGS and not (tags & _STORYTELLER_ONLY_TAGS):
                return False
            return True
