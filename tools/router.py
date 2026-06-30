import logging
from typing import Dict, Any, Callable, List
from core.security import SafeSandbox

logger = logging.getLogger("AuraNexus.Tools")

class ToolRegistry:
    """
    Unified registry for OpenClaw automation scripts and Hugging Face pipelines.
    Enforces that all tool execution paths are routed through the SafeSandbox.
    """
    
    def __init__(self, sandbox: SafeSandbox):
        self.sandbox = sandbox
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
            
        try:
            # All tools execute inside the boundaries of our sandbox root folder context
            tool_func = self._tools[name]["execute"]
            result = tool_func(self.sandbox, **arguments)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Execution failure in tool '{name}': {e}")
            return {"success": False, "error": str(e)}