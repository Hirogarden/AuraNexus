import logging
import inspect
import json
import psutil
from pathlib import Path
from dataclasses import dataclass
from typing import Generator, Any

from core.guardrails import normalize_response_length, response_length_prompt

try:
    from llama_cpp import Llama
    _LLAMA_IMPORT_ERROR: Exception | None = None
except ImportError as import_error:
    Llama = None
    _LLAMA_IMPORT_ERROR = import_error

logger = logging.getLogger("AuraNexus.Inference")


@dataclass(frozen=True)
class SamplingConfig:
    temperature: float
    max_tokens: int
    min_p: float
    dry_multiplier: float
    dry_base: float
    dry_allowed_length: int
    xtc_probability: float
    xtc_threshold: float


@dataclass(frozen=True)
class ResponseLengthPreset:
    max_tokens: int


@dataclass(frozen=True)
class ResponseLengthConfig:
    short: ResponseLengthPreset
    normal: ResponseLengthPreset
    long: ResponseLengthPreset

    def preset(self, mode: str) -> ResponseLengthPreset:
        return getattr(self, normalize_response_length(mode))


@dataclass(frozen=True)
class InferenceConfig:
    required_ram_buffer_mb: float
    n_gpu_layers: int
    ctx_size: int
    sampling: SamplingConfig
    response_lengths: ResponseLengthConfig


def _default_config_path() -> Path:
    return Path(__file__).resolve().with_name("inference_config.json")


def _validate_numeric_range(value: Any, name: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"Invalid config: '{name}' must be numeric.")
    float_value = float(value)
    if float_value < minimum or float_value > maximum:
        raise ValueError(
            f"Invalid config: '{name}' must be between {minimum} and {maximum}."
        )
    return float_value


def load_inference_config(config_path: str | Path | None = None) -> InferenceConfig:
    path = Path(config_path) if config_path else _default_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Inference config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("Invalid config: top-level inference config must be an object.")

    required_ram_buffer_mb = _validate_numeric_range(
        raw.get("required_ram_buffer_mb"),
        "required_ram_buffer_mb",
        256.0,
        1048576.0,
    )

    n_gpu_layers_raw = raw.get("n_gpu_layers")
    if not isinstance(n_gpu_layers_raw, int):
        raise ValueError("Invalid config: 'n_gpu_layers' must be an integer.")

    ctx_size_raw = raw.get("ctx_size")
    if not isinstance(ctx_size_raw, int) or ctx_size_raw < 256:
        raise ValueError("Invalid config: 'ctx_size' must be an integer >= 256.")

    sampling_raw = raw.get("sampling")
    if not isinstance(sampling_raw, dict):
        raise ValueError("Invalid config: 'sampling' must be an object.")

    max_tokens_raw = sampling_raw.get("max_tokens")
    if not isinstance(max_tokens_raw, int) or max_tokens_raw < 1:
        raise ValueError("Invalid config: 'sampling.max_tokens' must be an integer >= 1.")

    dry_allowed_length_raw = sampling_raw.get("dry_allowed_length")
    if not isinstance(dry_allowed_length_raw, int) or dry_allowed_length_raw < 1:
        raise ValueError(
            "Invalid config: 'sampling.dry_allowed_length' must be an integer >= 1."
        )

    sampling = SamplingConfig(
        temperature=_validate_numeric_range(
            sampling_raw.get("temperature"), "sampling.temperature", 0.0, 3.0
        ),
        max_tokens=max_tokens_raw,
        min_p=_validate_numeric_range(sampling_raw.get("min_p"), "sampling.min_p", 0.0, 1.0),
        dry_multiplier=_validate_numeric_range(
            sampling_raw.get("dry_multiplier"), "sampling.dry_multiplier", 0.0, 10.0
        ),
        dry_base=_validate_numeric_range(
            sampling_raw.get("dry_base"), "sampling.dry_base", 1.0, 10.0
        ),
        dry_allowed_length=dry_allowed_length_raw,
        xtc_probability=_validate_numeric_range(
            sampling_raw.get("xtc_probability"), "sampling.xtc_probability", 0.0, 1.0
        ),
        xtc_threshold=_validate_numeric_range(
            sampling_raw.get("xtc_threshold"), "sampling.xtc_threshold", 0.0, 1.0
        ),
    )

    response_lengths_raw = raw.get("response_lengths")
    if response_lengths_raw is None:
        response_lengths_raw = {
            "short": {"max_tokens": max(64, min(256, sampling.max_tokens // 2 or sampling.max_tokens))},
            "normal": {"max_tokens": sampling.max_tokens},
            "long": {"max_tokens": max(sampling.max_tokens, min(sampling.max_tokens * 2, 1024))},
        }

    if not isinstance(response_lengths_raw, dict):
        raise ValueError("Invalid config: 'response_lengths' must be an object.")

    def _load_length_preset(name: str) -> ResponseLengthPreset:
        preset_raw = response_lengths_raw.get(name)
        if not isinstance(preset_raw, dict):
            raise ValueError(f"Invalid config: 'response_lengths.{name}' must be an object.")
        max_tokens = preset_raw.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(
                f"Invalid config: 'response_lengths.{name}.max_tokens' must be an integer >= 1."
            )
        return ResponseLengthPreset(max_tokens=max_tokens)

    return InferenceConfig(
        required_ram_buffer_mb=required_ram_buffer_mb,
        n_gpu_layers=n_gpu_layers_raw,
        ctx_size=ctx_size_raw,
        sampling=sampling,
        response_lengths=ResponseLengthConfig(
            short=_load_length_preset("short"),
            normal=_load_length_preset("normal"),
            long=_load_length_preset("long"),
        ),
    )

class InferenceEngine:
    """
    Hardware-agnostic in-process llama.cpp inference engine for AuraNexus.
    Exposes configurable resource allocation and precision sampling parameters
    (Min-P, DRY, XTC) to maintain portable execution across diverse local machines.
    """
    
    def __init__(self, model_path: str | Path, config_path: str | Path | None = None):
        self.model_path = Path(model_path)
        self.model: Any = None
        self.config = load_inference_config(config_path)
        self.required_ram_buffer_mb = self.config.required_ram_buffer_mb
        self._max_tokens_override: int | None = None
        self._temperature_override: float | None = None
        self._response_length_mode: str = "normal"
        self._last_generation_hit_budget = False
        self._verify_system_resources()

    def set_generation_overrides(
        self,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_length: str | None = None,
    ) -> None:
        if max_tokens is not None and int(max_tokens) < 1:
            raise ValueError("max_tokens override must be >= 1")
        if temperature is not None and float(temperature) < 0.0:
            raise ValueError("temperature override must be >= 0")

        self._max_tokens_override = None if max_tokens is None else int(max_tokens)
        self._temperature_override = None if temperature is None else float(temperature)
        if response_length is not None:
            self._response_length_mode = normalize_response_length(response_length)

    def set_response_length_mode(self, mode: str) -> None:
        self._response_length_mode = normalize_response_length(mode)

    def get_response_length_mode(self) -> str:
        return self._response_length_mode

    def get_response_length_prompt(self) -> str:
        return response_length_prompt(self._response_length_mode)

    def get_response_length_max_tokens(self) -> int:
        if self._max_tokens_override is not None:
            return self._max_tokens_override
        return self.config.response_lengths.preset(self._response_length_mode).max_tokens

    @property
    def last_generation_hit_budget(self) -> bool:
        return self._last_generation_hit_budget

    def _verify_system_resources(self) -> None:
        """
        Enforces a safety buffer of free host system memory to protect the system 
        state prior to launching heavy model weight allocations.
        """
        available_ram_mb = psutil.virtual_memory().available / (1024 * 1024)
        if available_ram_mb < self.required_ram_buffer_mb:
            raise RuntimeError(
                f"Inference initialization aborted: Insufficient system memory. "
                f"Available: {available_ram_mb:.2f}MB, Required Safety Buffer: {self.required_ram_buffer_mb}MB."
            )
        logger.info("Host memory check complete. Hardware allocation window open.")

    def load_model(self, n_gpu_layers: int | None = None, ctx_size: int | None = None) -> None:
        """
        Loads the target GGUF model dynamically into memory.
        
        Parameters:
            n_gpu_layers (int): Number of layers to offload to the GPU. 
                                Set to 0 for pure CPU execution, or -1 to attempt 
                                full offloading if compiled with CUDA/Metal acceleration.
            ctx_size (int): Total context window allocation token size.
        """
        if Llama is None:
            raise RuntimeError(
                "llama_cpp is not installed. Install llama-cpp-python before loading models."
            ) from _LLAMA_IMPORT_ERROR

        if not self.model_path.exists():
            raise FileNotFoundError(f"Target model file not found: {self.model_path}")

        resolved_gpu_layers = self.config.n_gpu_layers if n_gpu_layers is None else n_gpu_layers
        resolved_ctx_size = self.config.ctx_size if ctx_size is None else ctx_size
            
        try:
            logger.info(f"Loading local model layer state: {self.model_path.name}")
            logger.info(
                f"Configuring offload execution lane: n_gpu_layers={resolved_gpu_layers}, "
                f"context={resolved_ctx_size}"
            )
            
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=resolved_ctx_size,
                n_gpu_layers=resolved_gpu_layers,
                f16_kv=True,
                verbose=False
            )
            logger.info("Model context mapping established successfully.")
        except Exception as e:
            logger.error(f"Failed to allocate model weights within the current hardware runtime: {e}")
            raise e

    def _assert_sampler_compatibility(self) -> None:
        completion_callable = getattr(self.model, "create_completion", None)
        if completion_callable is None:
            raise RuntimeError("Loaded model does not expose create_completion().")

        signature = inspect.signature(completion_callable)
        required_sampler_args = (
            "prompt",
            "max_tokens",
            "temperature",
            "stream",
        )

        supports_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

        if supports_kwargs:
            return

        missing = [arg for arg in required_sampler_args if arg not in signature.parameters]
        if missing:
            missing_text = ", ".join(missing)
            raise RuntimeError(
                "llama_cpp create_completion() does not support required completion parameters: "
                f"{missing_text}. Upgrade llama-cpp-python to a compatible version."
            )

    def _filter_supported_generation_kwargs(self, generation_kwargs: dict[str, Any]) -> dict[str, Any]:
        completion_callable = getattr(self.model, "create_completion", None)
        if completion_callable is None:
            raise RuntimeError("Loaded model does not expose create_completion().")

        signature = inspect.signature(completion_callable)
        supports_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        if supports_kwargs:
            return generation_kwargs

        filtered_kwargs = {
            name: value
            for name, value in generation_kwargs.items()
            if name in signature.parameters
        }
        skipped = sorted(set(generation_kwargs) - set(filtered_kwargs))
        if skipped:
            logger.warning(
                "Skipping unsupported llama_cpp sampler parameters: %s",
                ", ".join(skipped),
            )
        return filtered_kwargs

    def generate(self, prompt: str) -> Generator[str, None, None]:
        """
        Generates text tokens as a stream while applying advanced parameters
        to control repetition loops across multiple interaction styles.
        """
        if not self.model:
            raise RuntimeError("Engine execution blocked: Model has not been loaded.")

        self._assert_sampler_compatibility()
        sampling = self.config.sampling

        generation_kwargs = {
            "prompt": prompt,
            "max_tokens": self.get_response_length_max_tokens(),
            "temperature": (
                self._temperature_override
                if self._temperature_override is not None
                else sampling.temperature
            ),
            "stream": True,
            "min_p": sampling.min_p,
            "dry_multiplier": sampling.dry_multiplier,
            "dry_base": sampling.dry_base,
            "dry_allowed_length": sampling.dry_allowed_length,
            "xtc_probability": sampling.xtc_probability,
            "xtc_threshold": sampling.xtc_threshold,
        }
        generation_kwargs = self._filter_supported_generation_kwargs(generation_kwargs)

        try:
            self._last_generation_hit_budget = False
            response_stream = self.model.create_completion(**generation_kwargs)
            for chunk in response_stream:
                choice = chunk["choices"][0]
                if choice.get("finish_reason") == "length":
                    self._last_generation_hit_budget = True
                token_text = choice.get("text", "")
                if token_text:
                    yield token_text
        except TypeError as e:
            raise RuntimeError(
                "llama_cpp rejected configured sampling parameters. "
                "Install a compatible llama-cpp-python build that supports Min-P/DRY/XTC."
            ) from e
        except Exception as e:
            logger.error(f"Token generation interdiction: {e}")
            yield f"\n[Inference Runtime Warning: {e}]"