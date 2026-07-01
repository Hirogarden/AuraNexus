import json
from pathlib import Path
from typing import Any, Iterable

from core.inference import InferenceEngine
from core.runtime import AuraRuntime
from core.security import SafeSandbox
from modes.companion import CompanionMode, CompanionTurnResult
from modes.storyteller import StoryTurnResult, StorytellerMode
from storage.lorebook import LorebookManager
from storage.world_state import WorldState
from tools.executor import dispatch as _tool_dispatch, SKILL_SCHEMAS
from tools.hf_pipelines import HFPipelineRouter
from tools.openclaw_bridge import OpenClawBridge
from tools.router import ToolRegistry


def _default_bootstrap_world_facts(aura_name: str, user_name: str) -> list[dict[str, Any]]:
    return [
        {
            "key": "aura.name",
            "value": aura_name,
            "source": "system",
            "permanent": True,
        },
        {
            "key": "user.name",
            "value": user_name,
            "source": "system",
            "permanent": True,
        },
        {
            "key": "runtime.privacy_boundary",
            "value": "All file and tool actions remain inside the sandbox workspace.",
            "source": "system",
            "permanent": True,
        },
    ]


def _default_bootstrap_lore_cards(aura_name: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "companion-empathy-anchor",
            "keys": ["overwhelmed", "anxious", "uncertain"],
            "content": "Prioritize calm pacing, emotional clarity, and direct reassurance. Ask one grounded follow-up when needed.",
            "category": "behavior",
            "priority": 75,
            "enabled": True,
            "mode": "companion",
            "fuzzy_threshold": 0.88,
            "persona_id": aura_name,
            "state_tags": ["dialogue", "companion"],
        },
        {
            "id": "storyteller-continuity-anchor",
            "keys": ["ruins", "storm", "forest"],
            "content": "Maintain continuity, concrete sensory detail, and end each turn on an open moment that invites the next action.",
            "category": "narrative",
            "priority": 70,
            "enabled": True,
            "mode": "storyteller",
            "fuzzy_threshold": 0.88,
            "persona_id": None,
            "state_tags": ["story", "narrative"],
        },
    ]


class AuraNexusApp:
    """Top-level bootstrap container for sandbox, tools, runtime, and both mode lanes."""

    BOOTSTRAP_SCHEMA_VERSION = 2
    APP_VERSION = "0.2.0"

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
        self.state_dir = self.sandbox.sanitize_path("state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.bootstrap_path = self.sandbox.sanitize_path("state/bootstrap.json")
        self.inference_engine = InferenceEngine(model_path=model_path, config_path=config_path)
        self.lorebook = LorebookManager(data_path=self.sandbox.sanitize_path("state/lorebook.json"))
        self.world_state = WorldState(self.sandbox.sanitize_path("state/world_state.json"))
        self.tool_registry = ToolRegistry(sandbox=self.sandbox, allowed_commands=allowed_commands)
        self.openclaw_bridge = OpenClawBridge(sandbox=self.sandbox, registry_dir="skills")
        self.tool_registry.register_openclaw_skills(self.openclaw_bridge, auto_discover=True)
        self.hf_pipeline_router = HFPipelineRouter(sandbox=self.sandbox, pipeline_factory=pipeline_factory)
        self.tool_registry.register_hf_pipeline_tool(self.hf_pipeline_router)
        # Register built-in sandboxed skills (web_search, read_file, etc.)
        for schema in SKILL_SCHEMAS:
            fn_def = schema["function"]
            action_name = fn_def["name"]
            self.tool_registry.register_tool(
                name=action_name,
                description=fn_def["description"],
                parameters=fn_def["parameters"],
                func=lambda sb, _a=action_name, **kw: _tool_dispatch(_a, kw),
            )
        self.runtime = AuraRuntime(
            inference_engine=self.inference_engine,
            lorebook=self.lorebook,
            world_state=self.world_state,
            tool_registry=self.tool_registry,
            aura_name=aura_name,
            user_name=user_name,
            chat_session_dir=self.sandbox.sanitize_path("sessions/companion"),
            story_session_dir=self.sandbox.sanitize_path("sessions/story"),
            emotional_memory_dir=self.sandbox.sanitize_path("memory/emotional"),
        )
        self._apply_bootstrap_seed(aura_name=aura_name, user_name=user_name)
        self.companion_mode = CompanionMode(self.runtime)
        self.storyteller_mode = StorytellerMode(self.runtime)
        self._write_bootstrap_manifest(aura_name=aura_name, user_name=user_name)

    def _bootstrap_seed_payload(self, aura_name: str, user_name: str) -> dict[str, Any]:
        return {
            "world_facts": _default_bootstrap_world_facts(aura_name=aura_name, user_name=user_name),
            "lore_cards": _default_bootstrap_lore_cards(aura_name=aura_name),
        }

    def _apply_bootstrap_seed(self, aura_name: str, user_name: str) -> None:
        seed_payload = self._bootstrap_seed_payload(aura_name=aura_name, user_name=user_name)

        if not self.world_state.all_facts():
            for fact in seed_payload["world_facts"]:
                self.world_state.assert_fact(
                    key=str(fact["key"]),
                    value=str(fact["value"]),
                    source=str(fact.get("source", "system")),
                    permanent=bool(fact.get("permanent", False)),
                )

        if not self.lorebook.cards:
            from storage.lorebook import StoryCard

            for raw_card in seed_payload["lore_cards"]:
                if raw_card["id"] in self.lorebook.cards:
                    continue
                self.lorebook.add_card(StoryCard.from_dict(raw_card))

    def _write_bootstrap_manifest(self, aura_name: str, user_name: str) -> None:
        payload = {
            "schema_version": self.BOOTSTRAP_SCHEMA_VERSION,
            "app_version": self.APP_VERSION,
            "aura_name": aura_name,
            "user_name": user_name,
            "sandbox_root": str(self.sandbox.base_path),
            "world_state_path": str(self.world_state.data_path),
            "lorebook_path": str(self.lorebook.data_path) if self.lorebook.data_path is not None else None,
            "chat_session_dir": str(self.runtime.chat_session_dir) if self.runtime.chat_session_dir is not None else None,
            "story_session_dir": str(self.runtime.story_session_dir) if self.runtime.story_session_dir is not None else None,
            "skills_dir": str(self.openclaw_bridge.registry_dir),
            "bootstrap_seed": self._bootstrap_seed_payload(aura_name=aura_name, user_name=user_name),
        }
        self.bootstrap_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_bootstrap_manifest(self) -> dict[str, Any]:
        return json.loads(self.bootstrap_path.read_text(encoding="utf-8"))

    def load_model(self, n_gpu_layers: int | None = None, ctx_size: int | None = None) -> None:
        self.inference_engine.load_model(n_gpu_layers=n_gpu_layers, ctx_size=ctx_size)

    def save_state(self) -> None:
        self.lorebook.save()
        self.runtime.save_active_chat_session()
        self.runtime.save_active_story()
        self._write_bootstrap_manifest(aura_name=self.runtime.aura_name, user_name=self.runtime.user_name)

    def ensure_demo_skill(self) -> dict[str, Any]:
        tool_dir = self.sandbox.sanitize_path("skill_tools")
        tool_dir.mkdir(parents=True, exist_ok=True)
        script_path = tool_dir / "echo_demo.py"

        script_content = (
            "import argparse\n"
            "import json\n"
            "from pathlib import Path\n"
            "\n"
            "def main() -> int:\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--payload', required=True)\n"
            "    args = parser.parse_args()\n"
            "\n"
            "    payload_path = Path(args.payload)\n"
            "    payload = json.loads(payload_path.read_text(encoding='utf-8'))\n"
            "    arguments = payload.get('arguments', {})\n"
            "    text = str(arguments.get('text', ''))\n"
            "    result = {\n"
            "        'skill': payload.get('skill', 'demo_echo'),\n"
            "        'received_text': text,\n"
            "        'length': len(text),\n"
            "        'status': 'ok',\n"
            "    }\n"
            "    print(json.dumps(result, ensure_ascii=False))\n"
            "    return 0\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n"
        )
        script_path.write_text(script_content, encoding="utf-8")

        schema = {
            "name": "demo_echo",
            "description": "Echoes input text from sandbox payload for integration testing.",
            "parameters": {
                "text": {"type": "string"},
            },
            "required": ["text"],
            "command": ["python3", "skill_tools/echo_demo.py"],
            "allowed_binaries": ["python3"],
            "timeout": 30,
        }
        spec = self.openclaw_bridge.register_skill_schema(schema)
        self.tool_registry.register_openclaw_skills(self.openclaw_bridge, auto_discover=True)
        self._write_bootstrap_manifest(aura_name=self.runtime.aura_name, user_name=self.runtime.user_name)

        return {
            "skill_name": spec.name,
            "schema_path": str(self.openclaw_bridge.registry_dir / f"{spec.name}.schema.json"),
            "script_path": str(script_path),
        }

    def run_demo_skill(self, text: str, timeout: int = 30) -> dict[str, Any]:
        payload = {"text": str(text)}
        return self.tool_registry.execute_tool("demo_echo", payload)

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
