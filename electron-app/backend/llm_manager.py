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


def get_llm_instance():
    """Get the shared LLM instance (singleton pattern)"""
    return _llm_instance


def load_model(
    model_path: str,
    n_ctx: int = 4096,
    n_gpu_layers: int = 0,
    n_threads: Optional[int] = None,
    verbose: bool = False
) -> bool:
    """
    Load GGUF model into process memory
    
    Args:
        model_path: Path to .gguf model file
        n_ctx: Context window size (default 4096)
        n_gpu_layers: Number of layers to offload to GPU (0 = CPU only)
        n_threads: CPU threads to use (None = auto-detect)
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
        logger.info(f"  GPU layers: {n_gpu_layers}")
        
        # Load model into process memory
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_threads=n_threads,
            verbose=verbose,
            use_mlock=True,  # Lock model in RAM (prevents swapping)
            use_mmap=True,   # Use memory mapping for efficiency
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
    """Unload model from memory"""
    global _llm_instance, _model_path
    
    if _llm_instance is not None:
        logger.info("Unloading model from memory...")
        _llm_instance = None
        _model_path = None
        logger.info("Model unloaded")


def generate(
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
    stop: Optional[list] = None
) -> Optional[str]:
    """
    Generate text using in-process model
    
    Args:
        prompt: Input prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0-2.0)
        top_p: Nucleus sampling threshold
        top_k: Top-K sampling
        repeat_penalty: Repetition penalty
        stop: List of stop sequences
    
    Returns:
        Generated text or None if model not loaded
    """
    if _llm_instance is None:
        logger.warning("No model loaded, cannot generate")
        return None
    
    try:
        if stop is None:
            stop = ["\nUser:", "\n\n\n"]
        
        # Generate using in-process model
        result = _llm_instance(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=stop,
            echo=False  # Don't echo prompt in output
        )
        
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
            
            # Auto-detect GPU support
            n_gpu_layers = 0
            try:
                import torch
                if torch.cuda.is_available():
                    n_gpu_layers = 35  # Offload most layers to GPU
                    logger.info("CUDA detected, enabling GPU acceleration")
            except ImportError:
                pass
            
            return load_model(model_path, n_gpu_layers=n_gpu_layers)
    
    logger.warning("No models found in common locations")
    logger.info("Place .gguf model in ./models/ directory or specify path with load_model()")
    return False
