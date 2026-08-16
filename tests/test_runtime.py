from pathlib import Path

from core.runtime import AuraRuntime
from storage.lorebook import LorebookManager, StoryCard
from storage.story_session import StorySession
from storage.world_state import WorldState


class _StubToolRegistry:
    def get_tool_schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "hf_text_task",
                    "description": "Run text pipeline",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]


def test_world_state_persistence_and_permanent_guard(tmp_path: Path) -> None:
    state_path = tmp_path / "world_state.json"
    state = WorldState(state_path)
    state.assert_fact("aura.name", "Aura", source="system", permanent=True)
    state.assert_fact("user.name", "Hiro")
    state.assert_fact("aura.name", "Other", source="user")

    reloaded = WorldState(state_path)
    assert reloaded.get("aura.name") == "Aura"
    assert reloaded.get("user.name") == "Hiro"
    assert reloaded.retract_fact("aura.name") is False
    assert "do not contradict" in reloaded.as_prompt_block().lower()


def test_story_session_builds_prompt_and_round_trips(tmp_path: Path) -> None:
    session = StorySession(
        title="Ashes",
        genre="Fantasy",
        tone="Brooding",
        setting="A ruined kingdom under constant rain.",
        player_name="Mira",
        player_desc="A wandering knight",
    )
    session.add_beat("I light a torch.", "The flame trembles against the wet stone.")

    prompt = session.build_prompt("I open the gate.", extra_system="[World]\nRain never stops.")
    assert "Rain never stops." in prompt
    assert "Mira: I light a torch." in prompt

    save_path = tmp_path / "stories" / "ashes.json"
    session.save(save_path)
    loaded = StorySession.load(save_path)
    assert loaded.beats[0].narrator_response == "The flame trembles against the wet stone."


def test_runtime_builds_companion_prompt_with_world_lore_and_tools(tmp_path: Path) -> None:
    lorebook = LorebookManager()
    lorebook.add_card(
        StoryCard(
            id="trust-card",
            keys=["private trust"],
            content="Trust is fragile here.",
            mode="companion",
        )
    )
    world_state = WorldState(tmp_path / "world.json")
    world_state.assert_fact("user.preference", "prefers direct answers")

    runtime = AuraRuntime(
        inference_engine=object(),
        lorebook=lorebook,
        world_state=world_state,
        tool_registry=_StubToolRegistry(),
        aura_name="Aura",
        user_name="Hiro",
    )
    runtime.post_turn("hello", "hi")

    context = runtime.build_prompt("private trust matters")
    assert context.mode == "companion"
    # WorldState facts are STORYTELLER-ONLY; they must NOT appear in companion prompts.
    assert "prefers direct answers" not in context.prompt
    # Companion lore card should be included
    assert "Trust is fragile here." in context.prompt
    assert "hf_text_task" in context.prompt
    assert context.lore_card_ids == ["trust-card"]


def test_runtime_builds_story_prompt_and_records_beats(tmp_path: Path) -> None:
    lorebook = LorebookManager()
    lorebook.add_card(
        StoryCard(
            id="dragon-card",
            keys=["dragon"],
            content="The red dragon rules the mountain pass.",
            mode="storyteller",
        )
    )
    world_state = WorldState(tmp_path / "world.json")
    world_state.assert_fact("weather", "ashfall")

    runtime = AuraRuntime(inference_engine=object(), lorebook=lorebook, world_state=world_state)
    runtime.start_story(
        title="Pass of Cinders",
        genre="Fantasy",
        tone="Tense",
        setting="A volcanic borderland.",
        player_name="Mira",
    )

    context = runtime.build_prompt("I approach the dragon shrine.")
    assert context.mode == "storyteller"
    assert "ashfall" in context.prompt
    assert "red dragon rules the mountain pass" in context.prompt

    runtime.post_turn("I approach the dragon shrine.", "The shrine exhales sulfur and heat.")
    assert runtime.active_story is not None
    assert runtime.active_story.beats[0].narrator_response == "The shrine exhales sulfur and heat."