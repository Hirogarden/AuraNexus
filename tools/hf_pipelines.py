import gc
import json
from pathlib import Path
from typing import Any, Callable, Dict

from core.security import SafeSandbox


class HFPipelineError(RuntimeError):
    """Raised for invalid on-demand Hugging Face pipeline usage."""


_ALLOWED_TASKS = {
    "text-classification",
    "summarization",
    "feature-extraction",
    "text2text-generation",
    "token-classification",
}


class HFPipelineRouter:
    """On-demand local Hugging Face pipeline runner with explicit resource release."""

    def __init__(
        self,
        sandbox: SafeSandbox,
        pipeline_factory: Callable[..., Any] | None = None,
        device: int = -1,
    ):
        self.sandbox = sandbox
        self.device = device
        self._pipeline_factory = pipeline_factory

    @staticmethod
    def _validate_text(text: Any) -> str:
        if not isinstance(text, str) or not text.strip():
            raise HFPipelineError("Pipeline input must be a non-empty text string.")
        return text

    @staticmethod
    def _validate_task(task: Any) -> str:
        if not isinstance(task, str) or not task.strip():
            raise HFPipelineError("Pipeline task must be a non-empty string.")
        normalized = task.strip()
        if normalized not in _ALLOWED_TASKS:
            allowed = ", ".join(sorted(_ALLOWED_TASKS))
            raise HFPipelineError(f"Unsupported pipeline task '{normalized}'. Allowed tasks: {allowed}.")
        return normalized

    @staticmethod
    def _validate_options(options: Any) -> Dict[str, Any]:
        if options is None:
            return {}
        if not isinstance(options, dict):
            raise HFPipelineError("Pipeline options must be an object.")

        validated: Dict[str, Any] = {}
        for key, value in options.items():
            if not isinstance(key, str) or not key.strip():
                raise HFPipelineError("Pipeline options keys must be non-empty strings.")
            if isinstance(value, (str, int, float, bool)) or value is None:
                validated[key] = value
                continue
            if isinstance(value, list):
                if any(not isinstance(item, (str, int, float, bool, type(None))) for item in value):
                    raise HFPipelineError(
                        f"Pipeline option '{key}' contains non-serializable list values."
                    )
                validated[key] = value
                continue
            raise HFPipelineError(
                f"Pipeline option '{key}' has unsupported value type '{type(value).__name__}'."
            )
        return validated

    def _resolve_pipeline_factory(self) -> Callable[..., Any]:
        if self._pipeline_factory is not None:
            return self._pipeline_factory

        try:
            from transformers import pipeline  # type: ignore
        except Exception as exc:
            raise HFPipelineError(
                "transformers is not installed. Install it before running Hugging Face pipelines."
            ) from exc

        self._pipeline_factory = pipeline
        return pipeline

    def _append_audit_log(self, payload: Dict[str, Any]) -> None:
        audit_dir = self.sandbox.sanitize_path("hf_pipeline_runs")
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "history.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def run_text_task(
        self,
        task: str,
        text: str,
        model: str | None = None,
        options: Dict[str, Any] | None = None,
    ) -> Any:
        task_name = self._validate_task(task)
        text_payload = self._validate_text(text)
        run_options = self._validate_options(options)

        factory = self._resolve_pipeline_factory()
        pipeline_instance: Any = None
        try:
            if model is None:
                pipeline_instance = factory(task_name, device=self.device)
            else:
                if not isinstance(model, str) or not model.strip():
                    raise HFPipelineError("Model must be a non-empty string when provided.")
                pipeline_instance = factory(task_name, model=model.strip(), device=self.device)

            result = pipeline_instance(text_payload, **run_options)
            self._append_audit_log(
                {
                    "task": task_name,
                    "model": model,
                    "options": run_options,
                }
            )
            return result
        finally:
            pipeline_instance = None
            gc.collect()
