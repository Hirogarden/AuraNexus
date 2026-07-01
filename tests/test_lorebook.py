from storage.lorebook import LorebookManager, StoryCard
import pytest


def test_mode_separation_and_shared_cards() -> None:
    manager = LorebookManager()
    manager.add_card(
        StoryCard(
            id="companion-card",
            keys=["private trust"],
            content="Companion context",
            mode="companion",
            priority=100,
        )
    )
    manager.add_card(
        StoryCard(
            id="story-card",
            keys=["dragon"],
            content="Story context",
            mode="storyteller",
            priority=80,
        )
    )
    manager.add_card(
        StoryCard(
            id="shared-card",
            keys=["moonlit forest"],
            content="Shared context",
            mode="shared",
            priority=60,
        )
    )

    text = "The dragon crossed a moonlit forst while private trust was tested."

    storyteller_ids = {card.id for card in manager.scan_and_retrieve(text, mode="storyteller")}
    companion_ids = {card.id for card in manager.scan_and_retrieve(text, mode="companion")}

    assert "story-card" in storyteller_ids
    assert "shared-card" in storyteller_ids
    assert "companion-card" not in storyteller_ids

    assert "companion-card" in companion_ids
    assert "shared-card" in companion_ids
    assert "story-card" not in companion_ids


def test_phrase_and_fuzzy_triggering() -> None:
    phrase_card = StoryCard(id="p1", keys=["ancient order"], content="A")
    fuzzy_card = StoryCard(id="f1", keys=["shadow cathedral"], content="B")

    assert phrase_card.matches("The Ancient Order gathered at dawn.")
    assert fuzzy_card.matches("The shadow cathedrl stood silent in the valley.")


def test_forced_cards_and_scope_filters() -> None:
    manager = LorebookManager()
    manager.add_card(
        StoryCard(
            id="forced-card",
            keys=["never-used"],
            content="Forced context",
            mode="companion",
            persona_id="Aura",
            state_tags=["dialogue"],
            priority=50,
        )
    )
    manager.add_card(
        StoryCard(
            id="story-only",
            keys=["citadel"],
            content="Narrative context",
            mode="storyteller",
            state_tags=["story"],
        )
    )

    manager.set_active_persona("Aura")
    manager.set_active_state_tags(["dialogue", "companion"])
    manager.force_card("forced-card")
    cards = manager.scan_and_retrieve("plain text with no trigger", mode="companion")
    assert [card.id for card in cards] == ["forced-card"]

    cards_after_clear = manager.scan_and_retrieve("plain text with no trigger", mode="companion")
    assert cards_after_clear == []

    story_cards = manager.scan_and_retrieve(
        "The citadel waits.",
        mode="storyteller",
        state_tags=["story"],
    )
    assert [card.id for card in story_cards] == ["story-only"]


def test_story_card_enforces_key_and_threshold_constraints() -> None:
    with pytest.raises(ValueError, match="fuzzy_threshold"):
        StoryCard(
            id="bad-threshold",
            keys=["valid key"],
            content="content",
            fuzzy_threshold=0.2,
        )

    with pytest.raises(ValueError, match="<= 12 words"):
        StoryCard(
            id="bad-key",
            keys=["one two three four five six seven eight nine ten eleven twelve thirteen"],
            content="content",
        )


def test_lorebook_rejects_duplicate_card_ids() -> None:
    manager = LorebookManager()
    manager.add_card(StoryCard(id="dup", keys=["a"], content="first"))
    with pytest.raises(ValueError, match="already exists"):
        manager.add_card(StoryCard(id="dup", keys=["b"], content="second"))
