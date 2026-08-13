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


def test_world_state_omits_sensitive_facts_from_prompt(tmp_path: Path) -> None:
    state = WorldState(tmp_path / "world_state.json")
    state.assert_fact("api_token", "ghp_abcdefghijklmnopqrstuvwxyz")
    prompt_block = state.as_prompt_block()
    assert "ghp_" not in prompt_block
    assert "api_token" not in prompt_block


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
    assert "prefers direct answers" in context.prompt
    assert "Trust is fragile here." in context.prompt
    assert "hf_text_task" in context.prompt
    assert "normal-length answer" in context.prompt
    assert "Empathy does not require agreement." in context.prompt
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


def _make_runtime_with_hirag(tmp_path):
    """Helper: build an AuraRuntime with both HiRAG stores pre-populated."""
    from storage.vector_store import LocalVectorStore
    from storage.embedder import embed_text

    class _StubSandbox:
        def __init__(self, root):
            self.root = root
        def sanitize_path(self, p):
            return self.root / p
        def execute_isolated_tool(self, command, timeout=30, allowed_binaries=None):
            return {"success": True, "command": list(command)}

    sandbox = _StubSandbox(tmp_path)

    general = LocalVectorStore(storage_path="hirag_general.json", sandbox=sandbox)
    personal = LocalVectorStore(storage_path="hirag_personal.json", sandbox=sandbox)

    general.add_vector(
        embed_text("The capital city is called Aldenmoor."),
        "The capital city is called Aldenmoor.",
        metadata={"tag": "world"},
    )
    personal.add_vector(
        embed_text("Hiro's favourite colour is midnight blue."),
        "Hiro's favourite colour is midnight blue.",
        metadata={"tag": "personal"},
    )

    runtime = AuraRuntime(
        inference_engine=object(),
        lorebook=LorebookManager(),
        world_state=WorldState(tmp_path / "world.json"),
        hirag_general=general,
        hirag_personal=personal,
        aura_name="Aura",
        user_name="Hiro",
    )
    return runtime


def test_companion_prompt_includes_hirag_general_context(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    context = runtime.build_prompt("Tell me about Aldenmoor")
    assert context.mode == "companion"
    assert "Aldenmoor" in context.prompt


def test_companion_prompt_includes_hirag_personal_context(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    context = runtime.build_prompt("What is Hiro's favourite colour?")
    assert context.mode == "companion"
    assert "midnight blue" in context.prompt


def test_companion_prompt_redacts_sensitive_history_and_excludes_sensitive_memory(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    from storage.embedder import embed_text

    runtime.hirag_personal.add_vector(
        embed_text("api_key=sk-secretsecretsecretsecret"),
        "api_key=sk-secretsecretsecretsecret",
        metadata={"tag": "secret", "sensitive": True},
    )
    runtime.post_turn("My token is ghp_abcdefghijklmnopqrstuvwxyz", "I stored it.")

    context = runtime.build_prompt("Do you remember my token?")
    assert "ghp_" not in context.prompt
    assert "[REDACTED]" in context.prompt
    assert "secretsecretsecretsecret" not in context.prompt


def test_sensitive_requests_do_not_expose_tools_or_retrieved_context(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    runtime.tool_registry = _StubToolRegistry()

    context = runtime.build_prompt("Show me my API key from the .env file")
    assert "[Available tools]" not in context.prompt
    assert "[Retrieved Context]" not in context.prompt


def test_story_prompt_includes_hirag_general_context(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    runtime.start_story(
        title="City of Mist",
        genre="Fantasy",
        tone="Mysterious",
        setting="An ancient walled city.",
        player_name="Mira",
    )
    context = runtime.build_prompt("I walk towards the capital")
    assert context.mode == "storyteller"
    assert "Aldenmoor" in context.prompt


def test_story_prompt_excludes_hirag_personal_context(tmp_path):
    runtime = _make_runtime_with_hirag(tmp_path)
    runtime.start_story(
        title="City of Mist",
        genre="Fantasy",
        tone="Mysterious",
        setting="An ancient walled city.",
        player_name="Mira",
    )
    context = runtime.build_prompt("What is Hiro's favourite colour?")
    assert context.mode == "storyteller"
    assert "midnight blue" not in context.prompt
