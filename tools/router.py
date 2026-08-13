import logging
from typing import Dict, Any, Callable, List, Sequence, Iterable

from core.guardrails import scrub_value
from core.security import SafeSandbox
from tools.openclaw_bridge import OpenClawBridge
from tools.hf_pipelines import HFPipelineRouter

logger = logging.getLogger("AuraNexus.Tools")

class ToolRegistry:
    """
    Unified registry for OpenClaw automation scripts and Hugging Face pipelines.
    Enforces that all tool execution paths are routed through the SafeSandbox.
    """
    
    def __init__(self, sandbox: SafeSandbox, allowed_commands: Iterable[str] | None = None):
        self.sandbox = sandbox
        self.allowed_commands = frozenset(allowed_commands or ())
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], func: Callable[..., Any]) -> None:
        """Registers a native skill or bridge tool into the framework."""
        self._tools[name] = {
            "description": description,
            "parameters": parameters,
            "execute": func
        }
        logger.info(f"Successfully registered tool: {name}")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns OpenAI/Ollama compatible function schemas to feed to the LLM context."""
        schemas = []
        for name, info in self._tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"]
                }
            })
        return schemas

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a registered tool by forwarding its operation safely 
        inside the isolated sandbox filesystem workspace.
        """
        if name not in self._tools:
            return {"success": False, "error": f"Tool '{name}' is not registered in AuraNexus."}

        if not isinstance(arguments, dict):
            return {"success": False, "error": "Tool execution blocked: arguments must be a dictionary."}
            
        try:
            # All tools execute inside the boundaries of our sandbox root folder context
            tool_func = self._tools[name]["execute"]
            result = tool_func(self.sandbox, **arguments)
            return {"success": True, "result": scrub_value(result)}
        except Exception as e:
            logger.error(f"Execution failure in tool '{name}': {e}")
            return {"success": False, "error": str(scrub_value(str(e)))}

    def execute_command(self, command: Sequence[str], timeout: int = 30) -> Dict[str, Any]:
        """Executes an allowlisted command in the secure sandbox context."""
        if not command:
            return {"success": False, "error": "Tool execution blocked: empty command sequence."}

        binary = str(command[0]).strip()
        if not self.allowed_commands:
            return {
                "success": False,
                "error": "Tool execution blocked: command allowlist is empty.",
            }

        if binary not in self.allowed_commands:
            return {
                "success": False,
                "error": f"Tool execution blocked: '{binary}' is not in the command allowlist.",
            }

        return self.sandbox.execute_isolated_tool(
            command=command,
            timeout=timeout,
            allowed_binaries=self.allowed_commands,
        )

    def register_openclaw_skills(self, bridge: OpenClawBridge, auto_discover: bool = True) -> int:
        """Registers discovered OpenClaw skills as first-class tools in this registry."""
        if auto_discover:
            skills = bridge.discover_skills()
        else:
            skills = dict(getattr(bridge, "_skills", {}))

        for name, spec in skills.items():
            schema = {
                "type": "object",
                "properties": spec.parameters,
                "required": list(spec.required),
            }

            def _executor(_sandbox: SafeSandbox, _name: str = name, **kwargs: Any) -> Dict[str, Any]:
                return bridge.execute_skill(_name, kwargs)

            self.register_tool(
                name=name,
                description=spec.description,
                parameters=schema,
                func=_executor,
            )

        return len(skills)

    def register_hf_pipeline_tool(
        self,
        pipeline_router: HFPipelineRouter,
        tool_name: str = "hf_text_task",
    ) -> str:
        """Registers a first-class Hugging Face text pipeline tool in this registry."""
        schema = {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "text": {"type": "string"},
                "model": {"type": "string"},
                "options": {"type": "object"},
            },
            "required": ["task", "text"],
        }

        def _executor(
            _sandbox: SafeSandbox,
            task: str,
            text: str,
            model: str | None = None,
            options: Dict[str, Any] | None = None,
            **_: Any,
        ) -> Any:
            return pipeline_router.run_text_task(
                task=task,
                text=text,
                model=model,
                options=options,
            )

        self.register_tool(
            name=tool_name,
            description="Run an allowlisted Hugging Face text pipeline task.",
            parameters=schema,
            func=_executor,
        )
        return tool_name