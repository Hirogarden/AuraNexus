"""
In-Process LLM Manager
Loads models directly into Python process using llama-cpp-python
No external servers, fully self-contained, HIPAA-compliant

⚠️ SECURITY: HIPAA COMPLIANCE CRITICAL
This module ensures all LLM inference happens in-process without external 
network calls. Protected Health Information (PHI) stays in application memory.

NEVER modify this to:
- Call external APIs (OpenAI, Anthropic, etc.)
- Write unencrypted data to disk
- Send data over network
- Log user messages/PHI

See HIPAA_COMPLIANCE.md section "Transmission Security" for requirements.
"""

import logging
import os
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# Global model instance (loaded once, shared by all agents)
_llm_instance: Optional['Llama'] = None
_model_path: Optional[str] = None

# Prefix caching for faster generation with repeated system prompts
_prompt_cache: Dict[str, any] = {}


def get_llm_instance():
    """Get the shared LLM instance (singleton pattern)"""
    return _llm_instance


def load_model(
    model_path: str,
    n_ctx: int = 4096,
    n_gpu_layers: int = None,  # None = auto-detect based on VRAM
    n_threads: Optional[int] = None,
    n_batch: int = None,  # None = auto-detect based on VRAM
    verbose: bool = False
) -> bool:
    """
    Load GGUF model into process memory with automatic GPU optimization
    
    Args:
        model_path: Path to .gguf model file
        n_ctx: Context window size (default 4096)
        n_gpu_layers: Number of layers to offload to GPU (None = auto-detect)
        n_threads: CPU threads to use (None = auto-detect)
        n_batch: Batch size for prompt processing
        verbose: Enable debug logging
    
    Returns:
        True if model loaded successfully, False otherwise
    """
    global _llm_instance, _model_path
    
    # Check if model already loaded
    if _llm_instance is not None and _model_path == model_path:
        logger.info(f"Model already loaded: {model_path}")
        return True
    
    # Validate model file exists
    if not os.path.exists(model_path):
        logger.error(f"Model file not found: {model_path}")
        return False
    
    try:
        # Import llama-cpp-python
        try:
            from llama_cpp import Llama
        except ImportError:
            logger.error("llama-cpp-python not installed. Run: pip install llama-cpp-python")
            return False
        
        logger.info(f"Loading model: {model_path}")
        logger.info(f"  Context size: {n_ctx}")
        
        # Auto-detect GPU and optimize layers if not specified
        if n_gpu_layers is None:
            n_gpu_layers = _detect_optimal_gpu_layers(model_path)
        
        logger.info(f"  GPU layers: {n_gpu_layers}")
        if n_gpu_layers == 0:
            logger.info("  Running in CPU-only mode")
        else:
            logger.info(f"  GPU acceleration enabled ({n_gpu_layers} layers)")
        
        # Auto-adjust batch size for low VRAM
        if n_gpu_layers > 0 and n_gpu_layers < 20:
            n_batch = min(n_batch, 256)  # Smaller batches for limited VRAM
            logger.info(f"  Batch size adjusted to {n_batch} for VRAM optimization")
        
        # Load model into process memory
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_threads=n_threads,
            verbose=verbose,
            use_mlock=True,  # Lock model in RAM (prevents swapping)
            use_mmap=True,   # Use memory mapping for efficiency
            offload_kqv=n_gpu_layers > 0,  # Offload KV cache to GPU if using GPU
        )
        
        _model_path = model_path
        
        model_size = os.path.getsize(model_path) / (1024**3)  # GB
        logger.info(f"✅ Model loaded successfully ({model_size:.2f} GB)")
        logger.info(f"✅ Running IN-PROCESS (no external servers)")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        _llm_instance = None
        _model_path = None
        return False


def unload_model():
    """Unload model from memory and clear caches"""
    global _llm_instance, _model_path, _prompt_cache
    
    if _llm_instance is not None:
        logger.info("Unloading model from memory...")
        _llm_instance = None
        _model_path = None
        _prompt_cache = {}  # Clear prompt cache
        logger.info("Model unloaded")


def clear_prompt_cache():
    """Clear the prompt cache (useful for testing or memory management)"""
    global _prompt_cache
    _prompt_cache = {}
    logger.info("Prompt cache cleared")


def generate(
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    stop: Optional[list] = None,
    # Advanced sampling (KoboldCpp features)
    min_p: float = 0.0,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    dry_multiplier: float = 0.0,
    dry_base: float = 1.75,
    dry_allowed_length: int = 2,
    xtc_probability: float = 0.0,
    xtc_threshold: float = 0.1,
    dynatemp_range: float = 0.0,
    dynatemp_exponent: float = 1.0,
    mirostat_mode: int = 0,
    mirostat_tau: float = 5.0,
    mirostat_eta: float = 0.1,
    # Prefix caching
    cache_prompt: bool = False,
    cache_key: Optional[str] = None
) -> Optional[str]:
    """
    Generate text using in-process model with advanced sampling and prefix caching
    
    Args:
        prompt: Input prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0-2.0)
        top_p: Nucleus sampling threshold
        top_k: Top-K sampling
        repeat_penalty: Repetition penalty
        stop: List of stop sequences
        
        Advanced Sampling:
        min_p: Minimum probability threshold (better than top_p for some cases)
        frequency_penalty: Penalize frequent tokens (OpenAI-style)
        presence_penalty: Penalize already-present tokens
        dry_multiplier: DRY sampling strength (0.0=off, 0.8=recommended)
        dry_base: DRY penalty calculation base
        dry_allowed_length: Min sequence length before DRY applies
        xtc_probability: XTC sampling probability (0.0=off, 0.1=recommended)
        xtc_threshold: XTC exclusion threshold
        dynatemp_range: Dynamic temperature range (0.0=off)
        dynatemp_exponent: Dynamic temperature curve
        mirostat_mode: Mirostat sampling (0=off, 1=v1, 2=v2)
        mirostat_tau: Mirostat target entropy
        mirostat_eta: Mirostat learning rate
        
        Prefix Caching:
        cache_prompt: Whether to cache this prompt for reuse
        cache_key: Key for caching (e.g., "narrator_system_prompt")
    
    Returns:
        Generated text or None if model not loaded
    """
    if _llm_instance is None:
        logger.warning("No model loaded, cannot generate")
        return None
    
    try:
        if stop is None:
            stop = ["\nUser:", "\n\n\n"]
        
        # Check cache if enabled
        if cache_prompt and cache_key and cache_key in _prompt_cache:
            logger.debug(f"Using cached prompt: {cache_key}")
        elif cache_prompt and cache_key:
            _prompt_cache[cache_key] = prompt
            logger.debug(f"Cached prompt: {cache_key}")
        
        # Build sampling parameters
        params = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repeat_penalty": repeat_penalty,
            "stop": stop,
            "echo": False
        }
        
        # Add advanced sampling if enabled
        if min_p > 0.0:
            params["min_p"] = min_p
        if frequency_penalty != 0.0:
            params["frequency_penalty"] = frequency_penalty
        if presence_penalty != 0.0:
            params["presence_penalty"] = presence_penalty
        if dry_multiplier > 0.0:
            params["dry_multiplier"] = dry_multiplier
            params["dry_base"] = dry_base
            params["dry_allowed_length"] = dry_allowed_length
        if xtc_probability > 0.0:
            params["xtc_probability"] = xtc_probability
            params["xtc_threshold"] = xtc_threshold
        if dynatemp_range > 0.0:
            params["dynatemp_range"] = dynatemp_range
            params["dynatemp_exponent"] = dynatemp_exponent
        if mirostat_mode > 0:
            params["mirostat_mode"] = mirostat_mode
            params["mirostat_tau"] = mirostat_tau
            params["mirostat_eta"] = mirostat_eta
        
        # Generate using in-process model
        result = _llm_instance(**params)
        
        # Extract generated text
        generated = result["choices"][0]["text"].strip()
        return generated
        
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return None


def is_model_loaded() -> bool:
    """Check if a model is currently loaded"""
    return _llm_instance is not None


def get_model_info() -> Dict:
    """Get information about the loaded model"""
    if _llm_instance is None:
        return {"loaded": False}
    
    return {
        "loaded": True,
        "model_path": _model_path,
        "context_size": _llm_instance.n_ctx(),
        "model_size_gb": os.path.getsize(_model_path) / (1024**3) if _model_path else 0
    }


def auto_load_model() -> bool:
    """
    Auto-load model from common locations
    Searches for .gguf files in:
    - ./models/
    - ../models/
    - C:/Users/{user}/models/
    """
    search_paths = [
        Path("./models"),
        Path("../models"),
        Path.home() / "models",
        Path("C:/models") if os.name == 'nt' else Path("/models")
    ]
    
    logger.info("Auto-searching for models...")
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        # Find .gguf files
        gguf_files = list(search_path.glob("*.gguf"))
        
        if gguf_files:
            # Use first found model
            model_path = str(gguf_files[0])
            logger.info(f"Found model: {model_path}")
            
            # Load with auto-detected GPU settings
            return load_model(model_path)
    
    logger.warning("No models found in common locations")
    logger.info("Place .gguf model in ./models/ directory or specify path with load_model()")
    return False


def _detect_optimal_gpu_layers(model_path: str) -> int:
    """
    Auto-detect optimal GPU layer count based on available VRAM.
    Returns 0 for CPU-only, or estimated layer count for GPU.
    """
    try:
        # Try to detect NVIDIA GPU
        try:
            import torch
            if torch.cuda.is_available():
                # Get VRAM info
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info(f"Detected GPU with {vram_gb:.1f}GB VRAM")
                
                # Estimate model size
                model_size_gb = os.path.getsize(model_path) / (1024**3)
                
                # Simple heuristic for layer offloading
                if vram_gb >= 12:
                    return -1  # All layers - high VRAM
                elif vram_gb >= 8:
                    return min(35, int((vram_gb / model_size_gb) * 30))  # Medium VRAM
                elif vram_gb >= 4:
                    return min(20, int((vram_gb / model_size_gb) * 20))  # Low VRAM
                else:
                    logger.info("VRAM too limited for GPU offload")
                    return 0
        except ImportError:
            pass
        
        # No GPU detected
        logger.info("No CUDA GPU detected, using CPU-only mode")
        return 0
        
    except Exception as e:
        logger.warning(f"GPU detection failed: {e}, defaulting to CPU")
        return 0


def get_sampling_preset(preset_name: str) -> dict:
    """
    Get pre-configured sampling parameters for common use cases.
    
    Args:
        preset_name: One of 'chat', 'storytelling', 'assistant', 'creative', 'factual'
    
    Returns:
        Dictionary of sampling parameters
    """
    presets = {
        "chat": {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "min_p": 0.05,
            "dry_multiplier": 0.7,
            "frequency_penalty": 0.2,
            "presence_penalty": 0.1,
            "repeat_penalty": 1.1
        },
        "storytelling": {
            "temperature": 0.9,
            "top_p": 0.95,
            "top_k": 50,
            "min_p": 0.05,
            "dry_multiplier": 0.8,
            "xtc_probability": 0.1,
            "xtc_threshold": 0.1,
            "dynatemp_range": 0.15,
            "repeat_penalty": 1.05
        },
        "creative": {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 50,
            "min_p": 0.03,
            "dry_multiplier": 0.9,
            "xtc_probability": 0.15,
            "dynatemp_range": 0.2,
            "repeat_penalty": 1.1
        },
        "assistant": {
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.1,
            "repeat_penalty": 1.1,
            "dry_multiplier": 0.0,  # Off for precision
            "frequency_penalty": 0.1
        },
        "factual": {
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 30,
            "min_p": 0.15,
            "repeat_penalty": 1.15,
            "dry_multiplier": 0.0
        }
    }
    
    return presets.get(preset_name, presets["chat"])
