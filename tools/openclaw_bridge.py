import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

from core.security import SafeSandbox


class SkillRegistryError(RuntimeError):
    """Raised when skill schemas are invalid or execution is unsafe."""


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    required: tuple[str, ...]
    command: tuple[str, ...]
    timeout: int
    allowed_binaries: tuple[str, ...]

    @staticmethod
    def _expect_dict(value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise SkillRegistryError(f"Invalid skill schema: '{field_name}' must be an object.")
        return value

    @staticmethod
    def _expect_str(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise SkillRegistryError(f"Invalid skill schema: '{field_name}' must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _validate_binary_name(binary: str) -> str:
        if "/" in binary or "\\" in binary:
            raise SkillRegistryError(
                "Invalid skill schema: command binary must be a bare executable name."
            )
        return binary

    @staticmethod
    def _validate_command_tokens(command: tuple[str, ...]) -> tuple[str, ...]:
        validated: list[str] = []
        for token in command:
            value = str(token).strip()
            if not value:
                raise SkillRegistryError("Invalid skill schema: command entries must be non-empty strings.")

            # Permit regular flags, but reject absolute or traversal file references in command tokens.
            if value.startswith("/"):
                raise SkillRegistryError(
                    "Invalid skill schema: absolute command paths are forbidden. Use sandbox-relative paths."
                )
            if ".." in Path(value).parts:
                raise SkillRegistryError(
                    "Invalid skill schema: traversal operator '..' is forbidden in command tokens."
                )
            validated.append(value)
        return tuple(validated)

    @classmethod
    def from_schema(cls, schema: Dict[str, Any]) -> "SkillSpec":
        data = cls._expect_dict(schema, "schema")
        name = cls._expect_str(data.get("name"), "name")
        description = cls._expect_str(data.get("description"), "description")

        parameters = cls._expect_dict(data.get("parameters", {}), "parameters")

        required_raw = data.get("required", [])
        if not isinstance(required_raw, list) or any(not isinstance(item, str) for item in required_raw):
            raise SkillRegistryError("Invalid skill schema: 'required' must be a list of strings.")
        required = tuple(required_raw)

        command_raw = data.get("command")
        if not isinstance(command_raw, list) or not command_raw:
            raise SkillRegistryError("Invalid skill schema: 'command' must be a non-empty list.")
        command = cls._validate_command_tokens(tuple(str(item) for item in command_raw))

        binary = cls._validate_binary_name(command[0])

        timeout_raw = data.get("timeout", 30)
        if not isinstance(timeout_raw, int) or timeout_raw < 1 or timeout_raw > 600:
            raise SkillRegistryError("Invalid skill schema: 'timeout' must be an integer between 1 and 600.")

        allowed_raw = data.get("allowed_binaries")
        if allowed_raw is None:
            allowed_binaries = (binary,)
        else:
            if not isinstance(allowed_raw, list) or not allowed_raw:
                raise SkillRegistryError(
                    "Invalid skill schema: 'allowed_binaries' must be a non-empty list when provided."
                )
            normalized = []
            for item in allowed_raw:
                item_str = cls._expect_str(item, "allowed_binaries[]")
                normalized.append(cls._validate_binary_name(item_str))
            allowed_binaries = tuple(normalized)

        return cls(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            command=command,
            timeout=timeout_raw,
            allowed_binaries=allowed_binaries,
        )


class OpenClawBridge:
    """Dynamic local skill loader and executor with strict sandbox boundaries."""

    def __init__(
        self,
        sandbox: SafeSandbox,
        registry_dir: str | Path = "skills",
        schema_suffix: str = ".schema.json",
    ):
        self.sandbox = sandbox
        self.schema_suffix = schema_suffix
        self.registry_dir = self.sandbox.sanitize_path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, SkillSpec] = {}

    def _validate_arguments(self, spec: SkillSpec, arguments: Dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise SkillRegistryError("Skill execution blocked: arguments must be an object.")

        for key in spec.required:
            if key not in arguments:
                raise SkillRegistryError(
                    f"Skill execution blocked: missing required argument '{key}'."
                )

        for key, value in arguments.items():
            if key not in spec.parameters:
                raise SkillRegistryError(
                    f"Skill execution blocked: unexpected argument '{key}'."
                )

            expected_type = str(spec.parameters.get(key, {}).get("type", "any"))
            if expected_type == "string" and not isinstance(value, str):
                raise SkillRegistryError(f"Argument '{key}' must be a string.")
            if expected_type == "number" and not isinstance(value, (int, float)):
                raise SkillRegistryError(f"Argument '{key}' must be numeric.")
            if expected_type == "integer" and not isinstance(value, int):
                raise SkillRegistryError(f"Argument '{key}' must be an integer.")
            if expected_type == "boolean" and not isinstance(value, bool):
                raise SkillRegistryError(f"Argument '{key}' must be a boolean.")
            if expected_type == "object" and not isinstance(value, dict):
                raise SkillRegistryError(f"Argument '{key}' must be an object.")
            if expected_type == "array" and not isinstance(value, list):
                raise SkillRegistryError(f"Argument '{key}' must be an array.")

    def discover_skills(self) -> Dict[str, SkillSpec]:
        loaded: Dict[str, SkillSpec] = {}
        for schema_file in sorted(self.registry_dir.glob(f"*{self.schema_suffix}")):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    raw_schema = json.load(f)
            except Exception as exc:
                raise SkillRegistryError(
                    f"Failed to read skill schema '{schema_file.name}': {exc}"
                ) from exc

            spec = SkillSpec.from_schema(raw_schema)
            if spec.name in loaded:
                raise SkillRegistryError(
                    f"Duplicate skill name detected in registry: '{spec.name}'."
                )
            loaded[spec.name] = spec

        self._skills = loaded
        return dict(self._skills)

    def register_skill_schema(self, schema: Dict[str, Any]) -> SkillSpec:
        spec = SkillSpec.from_schema(schema)
        target = self.registry_dir / f"{spec.name}{self.schema_suffix}"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

        self._skills[spec.name] = spec
        return spec

    def get_tool_schemas(self) -> list[Dict[str, Any]]:
        schemas: list[Dict[str, Any]] = []
        for spec in self._skills.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": {
                            "type": "object",
                            "properties": spec.parameters,
                            "required": list(spec.required),
                        },
                    },
                }
            )
        return schemas

    def execute_skill(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._skills:
            raise SkillRegistryError(f"Skill '{name}' is not registered.")

        spec = self._skills[name]
        self._validate_arguments(spec, arguments)

        payload_dir = self.sandbox.sanitize_path("skill_payloads")
        payload_dir.mkdir(parents=True, exist_ok=True)
        payload_path = payload_dir / f"{name}.json"

        payload = {
            "skill": name,
            "arguments": arguments,
        }
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        command = list(spec.command) + ["--payload", str(payload_path)]
        return self.sandbox.execute_isolated_tool(
            command=command,
            timeout=spec.timeout,
            allowed_binaries=spec.allowed_binaries,
        )
