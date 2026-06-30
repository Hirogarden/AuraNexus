from storage.lorebook import LorebookManager, StoryCard


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
