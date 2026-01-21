"""
In-Process LLM Manager
Loads models directly into Python process using llama-cpp-python
No external servers, fully self-contained

⚠️ PRIVACY: All inference happens locally with no network calls
This module ensures all LLM inference happens in-process without external 
network calls. User data stays in application memory.

NEVER modify this to:
- Call external APIs (OpenAI, Anthropic, etc.)
- Write unencrypted data to disk
- Send data over network without explicit user consent
- Log user messages/data

User's model path:
"""
DEFAULT_MODEL_PATH = r"C:\Users\hirog\OneDrive\Desktop\4. Models\Llama-3.1-8B-Lexi-Uncensored-V2-Q8_0.gguf"

import logging
import os
from typing import Optional, Dict
from pathlib import Path

# Write to file to debug if module is loaded
with open("C:/Users/hirog/All-In-One/AuraNexus/python_debug.txt", "w") as f:
    f.write("[PYTHON] llm_manager.py MODULE IMPORTED!\n")

print("=" * 60, flush=True)
print("[PYTHON] llm_manager.py MODULE IMPORTED!", flush=True)
print("=" * 60, flush=True)

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
    n_batch: int = 512,  # Default batch size
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
        except ImportError as e:
            error_msg = f"llama-cpp-python not installed: {e}"
            logger.error(error_msg)
            print(f"[ERROR] {error_msg}", flush=True)
            return False
        
        logger.info(f"Loading model: {model_path}")
        print(f"[LOADING] Starting model load: {model_path}", flush=True)
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
            n_batch = 256  # Smaller batches for limited VRAM
            logger.info(f"  Batch size adjusted to {n_batch} for VRAM optimization")
        
        logger.info(f"  Batch size: {n_batch}")
        
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
        print(f"[SUCCESS] Model loaded! Size: {model_size:.2f} GB", flush=True)
        
        return True
        
    except Exception as e:
        error_msg = f"Failed to load model: {e}"
        logger.error(error_msg)
        print(f"[ERROR] {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        _llm_instance = None
        _model_path = None
        return False
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
    global _llm_instance
    
    # Auto-load model if not loaded
    if _llm_instance is None:
        logger.info("Model not loaded, attempting auto-load...")
        if os.path.exists(DEFAULT_MODEL_PATH):
            logger.info(f"Loading model from: {DEFAULT_MODEL_PATH}")
            success = load_model(DEFAULT_MODEL_PATH, n_ctx=4096, n_gpu_layers=33)
            if not success:
                logger.error("Failed to auto-load model")
                # Return mock response for testing
                mock_responses = [
                    "Hello! I'm AuraNexus running in test mode. The model hasn't been loaded yet, but the UI and backend are connected properly!",
                    "The UI looks great! Everything is connected properly. Once a language model is loaded, I'll be able to have real conversations with you.",
                    "I can see your messages are reaching me through the Rust → Python bridge successfully!",
                    "All systems operational! The Tauri frontend, Rust backend, and Python bridge are all working together."
                ]
                # Rotate through mock responses based on some state
                import hashlib
                response_index = int(hashlib.md5(prompt.encode()).hexdigest(), 16) % len(mock_responses)
                return mock_responses[response_index]
        else:
            logger.error(f"Model not found at: {DEFAULT_MODEL_PATH}")
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
        # Note: DRY, XTC, DynaTemp sampling removed - not supported by standard llama-cpp-python
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


def download_starter_model() -> Optional[str]:
    """
    Download a small starter model for out-of-box experience.
    Uses Qwen2.5-0.5B-Instruct (Q4_K_M quantization, ~350MB)
    
    Returns:
        Path to downloaded model, or None if download failed
    """
    try:
        import urllib.request
        from tqdm import tqdm
        
        # Small, capable model for trying out the app
        model_url = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
        model_name = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
        models_dir = Path("./models")
        models_dir.mkdir(exist_ok=True)
        model_path = models_dir / model_name
        
        if model_path.exists():
            logger.info(f"Starter model already exists: {model_path}")
            return str(model_path)
        
        logger.info("🚀 First-time setup: Downloading starter model (~350MB)...")
        logger.info("This lets you try AuraNexus immediately!")
        logger.info("You can upgrade to larger models later in Settings.")
        
        # Download with progress
        class DownloadProgressBar(tqdm):
            def update_to(self, b=1, bsize=1, tsize=None):
                if tsize is not None:
                    self.total = tsize
                self.update(b * bsize - self.n)
        
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1) as t:
            urllib.request.urlretrieve(
                model_url,
                model_path,
                reporthook=t.update_to
            )
        
        logger.info(f"✅ Starter model downloaded: {model_path}")
        return str(model_path)
        
    except Exception as e:
        logger.warning(f"Failed to download starter model: {e}")
        logger.info("You can manually download a .gguf model to ./models/")
        return None


def auto_load_model() -> bool:
    """
    Auto-load model from common locations or download starter model.
    Searches for .gguf files in:
    - ./models/
    - ../models/
    - C:/Users/{user}/models/
    
    If no model found, downloads a small starter model automatically.
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
    
    # No model found - try downloading starter model
    logger.info("No models found - attempting to download starter model...")
    starter_path = download_starter_model()
    
    if starter_path:
        return load_model(starter_path)
    
    logger.warning("No models available")
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
            "temperature": 0.4,  # Lower for small models to reduce rambling
            "top_p": 0.9,
            "top_k": 30,
            "min_p": 0.1,  # Higher min_p filters out weak tokens
            "frequency_penalty": 0.3,
            "presence_penalty": 0.2,
            "repeat_penalty": 1.2  # Higher to prevent repetition
        },
        "storytelling": {
            "temperature": 0.9,
            "top_p": 0.95,
            "top_k": 50,
            "min_p": 0.05,
            "repeat_penalty": 1.05
        },
        "creative": {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 50,
            "min_p": 0.03,
            "repeat_penalty": 1.1
        },
        "assistant": {
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.1,
            "repeat_penalty": 1.1,
            "frequency_penalty": 0.1
        },
        "factual": {
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 30,
            "min_p": 0.15,
            "repeat_penalty": 1.15
        }
    }
    
    return presets.get(preset_name, presets["chat"])


def find_available_model() -> Optional[str]:
    """
    Search for an available .gguf model in common locations.
    Used by Rust bridge to check if a model exists.
    
    Returns:
        Path to model if found, None otherwise
    """
    search_paths = [
        Path("./models"),
        Path("../models"),
        Path("../../models"),  # For Tauri development structure
        Path.home() / "models",
        Path("C:/models") if os.name == 'nt' else Path("/models")
    ]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        # Find .gguf files
        gguf_files = list(search_path.glob("*.gguf"))
        
        if gguf_files:
            model_path = str(gguf_files[0])
            logger.info(f"Found model: {model_path}")
            return model_path
    
    return None


def generate_with_context(
    prompt: str,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[list] = None,
    **kwargs
) -> str:
    """
    Generate response with conversation context.
    Called by Rust bridge with full conversation history.
    
    Args:
        prompt: Current user message
        system_prompt: System/personality prompt
        conversation_history: List of {role, content, timestamp} dicts
        **kwargs: Sampling parameters (temperature, top_p, etc.)
    
    Returns:
        Generated response text
    """
    global _llm_instance
    
    # Auto-load model if not loaded
    if _llm_instance is None:
        logger.info("[AUTO-LOAD] Model not loaded in generate_with_context(), attempting auto-load...")
        print("[AUTO-LOAD] Model not loaded, attempting auto-load...", flush=True)
        
        if os.path.exists(DEFAULT_MODEL_PATH):
            logger.info(f"[LOADING] Loading model from: {DEFAULT_MODEL_PATH}")
            print(f"[LOADING] Loading model from: {DEFAULT_MODEL_PATH}", flush=True)
            
            success = load_model(DEFAULT_MODEL_PATH, n_ctx=4096, n_gpu_layers=33)
            
            if not success:
                logger.error("[ERROR] Failed to auto-load model")
                print("[ERROR] Failed to auto-load model", flush=True)
                # Return mock response for testing
                mock_responses = [
                    "Hello! I'm AuraNexus running in test mode. A language model hasn't been loaded yet, so I'm responding with pre-programmed messages to verify the connection is working.",
                    "The UI looks great! Everything is connected properly. To get real AI responses, you'll need to download a GGUF model file.",
                    "I can see your messages are reaching me through the Rust → Python bridge successfully! Once you load a model, I'll be able to generate real responses.",
                    "All systems operational! The Tauri frontend, Rust backend, and Python bridge are all communicating correctly. Just waiting for a language model to be loaded.",
                ]
                # Rotate through responses
                response_index = len(conversation_history) % len(mock_responses) if conversation_history else 0
                return mock_responses[response_index]
            else:
                logger.info("[SUCCESS] Model loaded successfully!")
                print("[SUCCESS] Model loaded successfully!", flush=True)
        else:
            logger.error(f"[ERROR] Model not found at: {DEFAULT_MODEL_PATH}")
            print(f"[ERROR] Model not found at: {DEFAULT_MODEL_PATH}", flush=True)
            # Return error message
            return "Error: Model file not found. Please check the model path in settings."
    
    # If we reach here, model should be loaded
    if _llm_instance is None:
        return "Error: Model failed to load properly."
    
    # Build full prompt with context (using simpler format for small model)
    full_prompt_parts = []
    
    # Add system prompt if provided
    if system_prompt:
        full_prompt_parts.append(f"System: {system_prompt}\n\n")
    
    # Add conversation history (last 5 exchanges for context)
    if conversation_history:
        recent_history = conversation_history[-10:]  # Last 10 messages = 5 exchanges
        for entry in recent_history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            role_label = "User" if role == "user" else "Assistant"
            full_prompt_parts.append(f"{role_label}: {content}\n\n")
    
    # Add current prompt
    full_prompt_parts.append(f"User: {prompt}\n\nAssistant:")
    
    full_prompt = "".join(full_prompt_parts)
    
    # Add stop tokens to prevent model from outputting special tokens and continuing
    stop_sequences = [
        "\nUser:",
        "\nuser:",  
        "\nSystem:",
        "\nsystem:",
        "<|eot_id|>",
        "<|end_of_text|>",
        "<|im_end|>",
        "<|end_header_id|>",
        "<|start_header_id|>",
        "user<|end_header_id|>",
        "assistant<|end_header_id|>",
        "system<|end_header_id|>",
        "\n\n\n"  # Stop on excessive newlines
    ]
    
    # Override kwargs to include stop sequences
    kwargs['stop'] = stop_sequences
    
    # Generate with provided sampling parameters
    response = generate(
        prompt=full_prompt,
        **kwargs
    )
    
    if response is None:
        raise RuntimeError("Generation failed")
    
    # Clean up any special tokens that might have slipped through
    response = response.strip()
    
    # Remove all common special tokens
    special_tokens = [
        "<|eot_id|>",
        "<|end_of_text|>", 
        "<|im_end|>",
        "<|begin_of_text|>",
        "<|start_header_id|>",
        "<|end_header_id|>",
        "<|im_start|>",
        "[INST]",
        "[/INST]",
        "<<SYS>>",
        "<</SYS>>"
    ]
    
    for token in special_tokens:
        response = response.replace(token, "")
    
    # Also remove any remaining angle bracket patterns that look like tokens
    import re
    response = re.sub(r'<\|[^>]+\|>', '', response)
    response = re.sub(r'<[^>]+>', '', response)
    
    return response.strip()

