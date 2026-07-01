from pathlib import Path

from core.runtime import AuraRuntime
from modes.companion import CompanionMode
from modes.storyteller import StorytellerMode
from storage.chat_session import ChatSession
from storage.lorebook import LorebookManager, StoryCard
from storage.world_state import WorldState


class _StubInferenceEngine:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def generate(self, prompt: str):
        self.prompts.append(prompt)
        text = self.outputs.pop(0)
        for character in text:
            yield character


def test_chat_session_persistence_round_trip(tmp_path: Path) -> None:
    session = ChatSession(session_id="chat_1", name="Companion")
    session.add_turn("hello", "hi")
    path = tmp_path / "sessions" / "chat.json"
    session.save(path)

    restored = ChatSession.load(path)
    assert restored.turns[0].user_text == "hello"
    assert restored.recent_turns(1)[0].assistant_text == "hi"


def test_companion_mode_generates_hidden_reflection_and_persists_turn(tmp_path: Path) -> None:
    lorebook = LorebookManager()
    lorebook.add_card(
        StoryCard(
            id="care-card",
            keys=["uncertain"],
            content="Respond gently and directly.",
            mode="companion",
            persona_id="Aura",
            state_tags=["dialogue"],
        )
    )
    world_state = WorldState(tmp_path / "world.json")
    world_state.assert_fact("user.preference", "values calm pacing")
    engine = _StubInferenceEngine([
        "Notice anxiety, reassure without smothering.",
        "You are not alone in this. We can sort it out step by step.",
    ])

    runtime = AuraRuntime(
        inference_engine=engine,
        lorebook=lorebook,
        world_state=world_state,
        aura_name="Aura",
        user_name="Hiro",
    )
    runtime.start_chat_session("Primary")
    mode = CompanionMode(runtime)

    result = mode.generate_turn("I feel uncertain.")
    assert "Notice anxiety" in result.hidden_reflection
    assert "step by step" in result.response
    assert len(engine.prompts) == 2
    assert "Hidden Inner-Self Reflection" in engine.prompts[0]
    assert runtime.active_chat_session is not None
    assert runtime.active_chat_session.turns[0].assistant_text == result.response


def test_storyteller_mode_uses_runtime_prompt_and_records_story(tmp_path: Path) -> None:
    lorebook = LorebookManager()
    lorebook.add_card(
        StoryCard(
            id="ruin-card",
            keys=["ruins"],
            content="The ruins predate the empire.",
            mode="storyteller",
            state_tags=["story"],
        )
    )
    world_state = WorldState(tmp_path / "world.json")
    world_state.assert_fact("weather", "cold rain")
    engine = _StubInferenceEngine([
        "Cold rain drummed over the shattered arches as the ruins watched in silence.",
    ])

    runtime = AuraRuntime(inference_engine=engine, lorebook=lorebook, world_state=world_state)
    runtime.start_story(
        title="Broken Crown",
        genre="Fantasy",
        tone="Bleak",
        setting="A dead capital of wet stone.",
        player_name="Mira",
    )
    mode = StorytellerMode(runtime)

    result = mode.generate_turn("I enter the ruins.")
    assert "cold rain" in result.prompt_context.prompt
    assert "predate the empire" in result.prompt_context.prompt
    assert runtime.active_story is not None
    assert runtime.active_story.beats[0].narrator_response == result.response


def test_companion_mode_sanitizes_hidden_reflection_leakage(tmp_path: Path) -> None:
    engine = _StubInferenceEngine([
        "Reflect quietly before replying.",
        "When you answer User, try to reflect on your current emotional state.\n\n"
        "[hidden reflection:]\n"
        "Before answering User, think privately about your current emotional state.\n\n"
        "I can help with that.",
    ])

    runtime = AuraRuntime(inference_engine=engine, world_state=WorldState(tmp_path / "world.json"))
    runtime.start_chat_session("Primary")
    mode = CompanionMode(runtime)

    result = mode.generate_turn("hello")
    assert "hidden reflection" not in result.response.lower()
    assert "Before answering User" not in result.response
    assert "When you answer User" not in result.response
    assert result.response == "I can help with that."


def test_companion_mode_truncates_simulated_dialogue_tail(tmp_path: Path) -> None:
    engine = _StubInferenceEngine([
        "Brief reflection.",
        "I hear you.\nUser: I am feeling sad.\nAura: Tell me more.",
    ])

    runtime = AuraRuntime(inference_engine=engine, world_state=WorldState(tmp_path / "world.json"))
    runtime.start_chat_session("Primary")
    mode = CompanionMode(runtime)

    result = mode.generate_turn("hello")
    assert result.response == "I hear you."