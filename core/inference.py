import logging
import os
import psutil
from pathlib import Path
from typing import List, Dict, Any, Generator

try:
    from llama_cpp import Llama
except ImportError:
    class Llama:
        def __init__(self, *args, **kwargs): pass
        def __call__(self, *args, **kwargs): return {}
        def create_completion(self, *args, **kwargs): return {}

logger = logging.getLogger("AuraNexus.Inference")

class InferenceEngine:
    """
    Hardware-agnostic in-process llama.cpp inference engine for AuraNexus.
    Exposes configurable resource allocation and precision sampling parameters
    (Min-P, DRY, XTC) to maintain portable execution across diverse local machines.
    """
    
    def __init__(self, model_path: str | Path, required_ram_buffer_mb: float = 2048.0):
        self.model_path = Path(model_path)
        self.model = None
        self.required_ram_buffer_mb = required_ram_buffer_mb
        self._verify_system_resources()

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

    def load_model(self, n_gpu_layers: int = 0, ctx_size: int = 4096) -> None:
        """
        Loads the target GGUF model dynamically into memory.
        
        Parameters:
            n_gpu_layers (int): Number of layers to offload to the GPU. 
                                Set to 0 for pure CPU execution, or -1 to attempt 
                                full offloading if compiled with CUDA/Metal acceleration.
            ctx_size (int): Total context window allocation token size.
        """
        if not self.model_path.exists():
            raise FileNotFoundError(f"Target model file not found: {self.model_path}")
            
        try:
            logger.info(f"Loading local model layer state: {self.model_path.name}")
            logger.info(f"Configuring offload execution lane: n_gpu_layers={n_gpu_layers}, context={ctx_size}")
            
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=ctx_size,
                n_gpu_layers=n_gpu_layers, 
                f16_kv=True,
                verbose=False
            )
            logger.info("Model context mapping established successfully.")
        except Exception as e:
            logger.error(f"Failed to allocate model weights within the current hardware runtime: {e}")
            raise e

    def generate(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        temperature: float = 0.8,
        min_p: float = 0.05,
        dry_multiplier: float = 0.8,
        dry_base: float = 1.75,
        dry_allowed_length: int = 2,
        xtc_probability: float = 0.1,
        xtc_threshold: float = 0.1
    ) -> Generator[str, None, None]:
        """
        Generates text tokens as a stream while applying advanced parameters
        to control repetition loops across multiple interaction styles.
        """
        if not self.model:
            raise RuntimeError("Engine execution blocked: Model has not been loaded.")

        generation_kwargs = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "min_p": min_p,
        }

        # Check for modular advanced sampler compatibility inside the runtime version
        if hasattr(self.model, "dry_multiplier") or "dry_multiplier" in getattr(Llama, "__init__").__code__.co_varnames:
            generation_kwargs["dry_multiplier"] = dry_multiplier
            generation_kwargs["dry_base"] = dry_base
            generation_kwargs["dry_allowed_length"] = dry_allowed_length
            
        if "xtc_probability" in generation_kwargs or hasattr(self.model, "xtc_probability"):
            generation_kwargs["xtc_probability"] = xtc_probability
            generation_kwargs["xtc_threshold"] = xtc_threshold

        try:
            response_stream = self.model.create_completion(**generation_kwargs)
            for chunk in response_stream:
                token_text = chunk["choices"][0]["text"]
                if token_text:
                    yield token_text
        except Exception as e:
            logger.error(f"Token generation interdiction: {e}")
            yield f"\n[Inference Runtime Warning: {e}]"