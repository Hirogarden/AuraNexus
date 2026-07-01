from pathlib import Path
from typing import Any, Iterable

from core.inference import InferenceEngine
from core.runtime import AuraRuntime
from core.security import SafeSandbox
from modes.companion import CompanionMode, CompanionTurnResult
from modes.storyteller import StoryTurnResult, StorytellerMode
from storage.lorebook import LorebookManager
from storage.world_state import WorldState
from tools.hf_pipelines import HFPipelineRouter
from tools.openclaw_bridge import OpenClawBridge
from tools.router import ToolRegistry


class AuraNexusApp:
    """Top-level bootstrap container for sandbox, tools, runtime, and both mode lanes."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        workspace_dir: str | Path = "sandbox_workspace",
        config_path: str | Path | None = None,
        aura_name: str = "Aura",
        user_name: str = "User",
        allowed_commands: Iterable[str] | None = None,
        require_isolation: bool = True,
        pipeline_factory: Any = None,
    ) -> None:
        self.sandbox = SafeSandbox(
            workspace_dir=workspace_dir,
            allowed_binaries=allowed_commands,
            require_isolation=require_isolation,
        )
        self.inference_engine = InferenceEngine(model_path=model_path, config_path=config_path)
        self.lorebook = LorebookManager()
        self.world_state = WorldState(self.sandbox.sanitize_path("state/world_state.json"))
        self.tool_registry = ToolRegistry(sandbox=self.sandbox, allowed_commands=allowed_commands)
        self.openclaw_bridge = OpenClawBridge(sandbox=self.sandbox, registry_dir="skills")
        self.tool_registry.register_openclaw_skills(self.openclaw_bridge, auto_discover=True)
        self.hf_pipeline_router = HFPipelineRouter(sandbox=self.sandbox, pipeline_factory=pipeline_factory)
        self.tool_registry.register_hf_pipeline_tool(self.hf_pipeline_router)
        self.runtime = AuraRuntime(
            inference_engine=self.inference_engine,
            lorebook=self.lorebook,
            world_state=self.world_state,
            tool_registry=self.tool_registry,
            aura_name=aura_name,
            user_name=user_name,
            chat_session_dir=self.sandbox.sanitize_path("sessions/companion"),
            story_session_dir=self.sandbox.sanitize_path("sessions/story"),
        )
        self.companion_mode = CompanionMode(self.runtime)
        self.storyteller_mode = StorytellerMode(self.runtime)

    def load_model(self, n_gpu_layers: int | None = None, ctx_size: int | None = None) -> None:
        self.inference_engine.load_model(n_gpu_layers=n_gpu_layers, ctx_size=ctx_size)

    def ensure_companion_session(self, name: str | None = None, restore_latest: bool = True) -> None:
        self.runtime.ensure_chat_session(name=name, restore_latest=restore_latest)

    def generate_companion_turn(
        self,
        user_input: str,
        *,
        session_name: str | None = None,
        restore_latest: bool = True,
    ) -> CompanionTurnResult:
        self.ensure_companion_session(name=session_name, restore_latest=restore_latest)
        return self.companion_mode.generate_turn(user_input)

    def start_story(self, **kwargs: Any) -> None:
        self.runtime.start_story(**kwargs)

    def generate_story_turn(self, user_input: str) -> StoryTurnResult:
        if self.runtime.active_story is None:
            raise RuntimeError("No active story session has been started.")
        return self.storyteller_mode.generate_turn(user_input)
