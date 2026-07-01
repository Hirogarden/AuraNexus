from pathlib import Path
import json

from core.app import AuraNexusApp
from core.runtime import AuraRuntime
from core.security import SafeSandbox
from modes.companion import CompanionMode
from storage.chat_session import ChatSession
from storage.lorebook import LorebookManager
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


def test_runtime_auto_restores_latest_chat_session(tmp_path: Path) -> None:
    runtime = AuraRuntime(
        inference_engine=_StubInferenceEngine([]),
        lorebook=LorebookManager(),
        world_state=WorldState(tmp_path / "world.json"),
        chat_session_dir=tmp_path / "chat_sessions",
    )
    first = runtime.start_chat_session("Primary")
    runtime.post_turn("hello", "hi")
    runtime.attach_chat_session(None)

    restored = runtime.ensure_chat_session(restore_latest=True)
    assert restored.session_id == first.session_id
    assert restored.turns[0].assistant_text == "hi"


def test_runtime_lists_and_loads_chat_sessions(tmp_path: Path) -> None:
    runtime = AuraRuntime(
        inference_engine=_StubInferenceEngine([]),
        lorebook=LorebookManager(),
        world_state=WorldState(tmp_path / "world.json"),
        chat_session_dir=tmp_path / "chat_sessions",
    )
    session = ChatSession(session_id="chat_1", name="Primary")
    session.add_turn("one", "two")
    session.save((tmp_path / "chat_sessions" / "chat_1.json"))

    listing = runtime.list_chat_sessions()
    assert listing[0]["session_id"] == "chat_1"

    restored = runtime.load_chat_session("chat_1")
    assert restored.turns[0].user_text == "one"


def test_app_bootstrap_uses_sandbox_paths_and_registers_default_tools(tmp_path: Path, monkeypatch) -> None:
    class _FakeInferenceEngine:
        def __init__(self, model_path, config_path=None):
            self.model_path = Path(model_path)
            self.config_path = config_path

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            return None

        def generate(self, prompt: str):
            yield "ok"

    monkeypatch.setattr("core.app.InferenceEngine", _FakeInferenceEngine)

    app = AuraNexusApp(
        model_path=tmp_path / "model.gguf",
        workspace_dir=tmp_path / "sandbox_workspace",
        allowed_commands={"python3"},
        require_isolation=False,
        pipeline_factory=lambda *args, **kwargs: lambda text, **opts: [{"label": "OK", "score": 1.0}],
    )

    assert isinstance(app.sandbox, SafeSandbox)
    assert app.runtime.chat_session_dir == app.sandbox.sanitize_path("sessions/companion")
    tool_names = [schema["function"]["name"] for schema in app.tool_registry.get_tool_schemas()]
    assert "hf_text_task" in tool_names
    manifest = app.get_bootstrap_manifest()
    assert manifest["schema_version"] == 2
    assert manifest["lorebook_path"].endswith("state/lorebook.json")
    assert manifest["bootstrap_seed"]["world_facts"][0]["key"] == "aura.name"


def test_app_reloads_lorebook_and_world_state_from_same_sandbox_root(tmp_path: Path, monkeypatch) -> None:
    class _FakeInferenceEngine:
        def __init__(self, model_path, config_path=None):
            self.model_path = Path(model_path)
            self.config_path = config_path

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            return None

        def generate(self, prompt: str):
            yield "ok"

    monkeypatch.setattr("core.app.InferenceEngine", _FakeInferenceEngine)

    workspace = tmp_path / "sandbox_workspace"
    app = AuraNexusApp(
        model_path=tmp_path / "model.gguf",
        workspace_dir=workspace,
        allowed_commands={"python3"},
        require_isolation=False,
        pipeline_factory=lambda *args, **kwargs: lambda text, **opts: [{"label": "OK", "score": 1.0}],
    )
    app.lorebook.add_card(
        app.lorebook.cards.get("card") or __import__("storage.lorebook", fromlist=["StoryCard"]).StoryCard(
            id="card",
            keys=["embers"],
            content="The embers never die.",
            mode="storyteller",
        )
    )
    app.world_state.assert_fact("weather", "ashfall")
    app.save_state()

    reloaded = AuraNexusApp(
        model_path=tmp_path / "model.gguf",
        workspace_dir=workspace,
        allowed_commands={"python3"},
        require_isolation=False,
        pipeline_factory=lambda *args, **kwargs: lambda text, **opts: [{"label": "OK", "score": 1.0}],
    )
    assert "card" in reloaded.lorebook.cards
    assert reloaded.world_state.get("weather") == "ashfall"


def test_app_seeds_default_world_state_and_lorebook_on_first_run(tmp_path: Path, monkeypatch) -> None:
    class _FakeInferenceEngine:
        def __init__(self, model_path, config_path=None):
            self.model_path = Path(model_path)
            self.config_path = config_path

        def load_model(self, n_gpu_layers=None, ctx_size=None):
            return None

        def generate(self, prompt: str):
            yield "ok"

    monkeypatch.setattr("core.app.InferenceEngine", _FakeInferenceEngine)

    app = AuraNexusApp(
        model_path=tmp_path / "model.gguf",
        workspace_dir=tmp_path / "sandbox_workspace",
        allowed_commands={"python3"},
        require_isolation=False,
        aura_name="Aura",
        user_name="Hiro",
        pipeline_factory=lambda *args, **kwargs: lambda text, **opts: [{"label": "OK", "score": 1.0}],
    )

    assert app.world_state.get("aura.name") == "Aura"
    assert app.world_state.get("user.name") == "Hiro"
    assert "companion-empathy-anchor" in app.lorebook.cards
    assert "storyteller-continuity-anchor" in app.lorebook.cards


def test_companion_mode_switches_runtime_mode_per_turn(tmp_path: Path) -> None:
    runtime = AuraRuntime(
        inference_engine=_StubInferenceEngine(["reflect", "reply"]),
        lorebook=LorebookManager(),
        world_state=WorldState(tmp_path / "world.json"),
        chat_session_dir=tmp_path / "chat_sessions",
    )
    runtime.start_chat_session("Primary")
    runtime.set_mode("storyteller")

    result = CompanionMode(runtime).generate_turn("hello")
    assert result.response == "reply"
    assert runtime.mode == "companion"