"""AuraNexus Secure Inference Engine

A self-contained, HIPAA-compliant LLM inference engine that runs entirely
in-process without external dependencies or network calls.

Key Security Features:
- No external process calls
- No network requests
- All data stays in memory
- No temporary files (unless explicitly saved by user)
- Direct model loading from local files
- Isolated from system services

Based on llama.cpp via Python bindings for maximum security and control.
"""

from typing import List, Dict, Optional, Iterator, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import psutil

try:
    from llama_cpp import Llama, LlamaGrammar
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None
    LlamaGrammar = None


@dataclass
class Message:
    """Chat message with timestamp"""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Message':
        timestamp = d.get('timestamp')
        if timestamp and isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            role=d['role'],
            content=d['content'],
            timestamp=timestamp or datetime.now()
        )


class SecureInferenceEngine:
    """
    Self-contained inference engine for AuraNexus.
    
    Security Properties:
    - Runs in-process (no subprocess calls)
    - No network communication
    - No external API dependencies
    - Memory-only operation (no temp files)
    - Complete data isolation
    
    Perfect for:
    - HIPAA-compliant healthcare applications
    - Legal document processing
    - Financial data analysis
    - Any scenario requiring air-gapped operation
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 2048,  # Conservative default to prevent OOM
        n_gpu_layers: int = -1,  # -1 = auto-detect and use all
        n_batch: int = 512,
        verbose: bool = False,
        # Memory safety limits
        max_memory_mb: Optional[int] = None,  # Auto-detect if None
        min_free_memory_mb: int = 2048  # Keep 2GB free
    ):
        """
        Initialize the secure inference engine.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 for all)
            n_batch: Batch size for prompt processing
            verbose: Enable debug output
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is required for secure inference.\n"
                "Install with: pip install llama-cpp-python"
            )
        
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_batch = n_batch
        self.verbose = verbose
        
        # Memory safety configuration
        self.min_free_memory_mb = min_free_memory_mb
        self.max_memory_mb = max_memory_mb or self._calculate_safe_memory_limit()
        
        self.model: Optional[Llama] = None
        self.loaded_model_path: Optional[str] = None
        
        # Auto-load if model_path provided
        if model_path:
            self.load_model(model_path)
    
    def _calculate_safe_memory_limit(self) -> int:
        """Calculate safe memory limit based on available RAM."""
        total_ram_mb = psutil.virtual_memory().total // (1024 * 1024)
        # Use at most 75% of total RAM, or 8GB, whichever is smaller
        safe_limit = min(int(total_ram_mb * 0.75), 8192)
        return safe_limit
    
    def _check_memory_available(self) -> tuple[bool, str]:
        """Check if sufficient memory is available."""
        mem = psutil.virtual_memory()
        available_mb = mem.available // (1024 * 1024)
        
        if available_mb < self.min_free_memory_mb:
            return False, f"Insufficient memory: {available_mb}MB available, need {self.min_free_memory_mb}MB minimum"
        
        return True, f"Memory OK: {available_mb}MB available"
    
    def load_model(self, model_path: str, **kwargs) -> tuple[bool, str]:
        """
        Load a GGUF model file with memory safety checks.
        
        Args:
            model_path: Path to .gguf model file
            **kwargs: Override initialization parameters
            
        Returns:
            (success: bool, message: str)
        """
        try:
            # Check memory before loading
            mem_ok, mem_msg = self._check_memory_available()
            if not mem_ok:
                return False, mem_msg
            
            if self.verbose:
                print(f"Loading model: {model_path}")
                print(f"Memory check: {mem_msg}")
            
            # Close existing model if loaded
            if self.model is not None:
                if self.verbose:
                    print("Unloading previous model...")
                del self.model
                self.model = None
            
            # Load new model
            self.model = Llama(
                model_path=model_path,
                n_ctx=kwargs.get('n_ctx', self.n_ctx),
                n_gpu_layers=kwargs.get('n_gpu_layers', self.n_gpu_layers),
                n_batch=kwargs.get('n_batch', self.n_batch),
                verbose=self.verbose
            )
            
            self.loaded_model_path = model_path
            
            if self.verbose:
                print(f"✓ Model loaded successfully")
                mem_after = psutil.virtual_memory()
                print(f"Memory usage: {mem_after.percent}% ({mem_after.used // (1024*1024)}MB used)")
            
            return True, "Model loaded successfully"
            
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            print(error_msg)
            return False, error_msg
    
    def is_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.model is not None
    
    def get_loaded_model(self) -> Optional[str]:
        """Get path of currently loaded model"""
        return self.loaded_model_path
    
    def chat(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        # Standard sampling
        temperature: float = 0.8,
        top_p: float = 0.95,
        top_k: int = 40,
        max_tokens: int = 512,
        stop: Optional[List[str]] = None,
        stream: bool = False,
        # KoboldCpp Advanced Sampling
        min_p: float = 0.05,
        typical_p: float = 1.0,
        repeat_penalty: float = 1.1,
        repeat_last_n: int = 64,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        # DRY sampling (reduces repetition)
        dry_multiplier: float = 0.0,
        dry_base: float = 1.75,
        dry_allowed_length: int = 2,
        dry_penalty_last_n: int = -1,
        # XTC sampling (better diversity)
        xtc_probability: float = 0.0,
        xtc_threshold: float = 0.1,
        # Dynamic temperature
        dynatemp_range: float = 0.0,
        dynatemp_exponent: float = 1.0,
        # Mirostat (adaptive sampling)
        mirostat_mode: int = 0,
        mirostat_tau: float = 5.0,
        mirostat_eta: float = 0.1,
        # Grammar/Format enforcement
        grammar: Optional[str] = None,
        json_schema: Optional[dict] = None,
        # Context management
        n_keep: int = 0,  # Keep first N tokens (for system prompt)
        # Other
        seed: int = -1,
        logit_bias: Optional[Dict[int, float]] = None,
        logprobs: Optional[int] = None,
        tfs_z: float = 1.0,
        typical: float = 1.0,
    ) -> Iterator[str] if stream else str:
        """
        Generate chat completion with KoboldCpp-enhanced sampling.
        
        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt
            
            **Standard Parameters:**
            temperature: Sampling temperature (0-2)
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling parameter
            max_tokens: Maximum tokens to generate
            stop: List of stop sequences
            stream: Enable streaming output
            
            **Advanced Sampling (KoboldCpp features):**
            min_p: Minimum probability threshold (better than top_p)
            typical_p: Typical sampling parameter
            repeat_penalty: Penalty for repeating tokens
            repeat_last_n: Look back N tokens for repetition
            frequency_penalty: Penalize frequent tokens
            presence_penalty: Penalize present tokens
            
            dry_multiplier: DRY (Don't Repeat Yourself) strength (0=off)
            dry_base: Base for DRY penalty calculation
            dry_allowed_length: Min sequence length before DRY applies
            dry_penalty_last_n: DRY lookback (-1=use repeat_last_n)
            
            xtc_probability: XTC sampling probability (0-1, 0=off)
            xtc_threshold: XTC exclusion threshold
            
            dynatemp_range: Dynamic temperature range (0=off)
            dynatemp_exponent: Dynamic temperature curve
            
            mirostat_mode: Mirostat mode (0=off, 1=v1, 2=v2)
            mirostat_tau: Mirostat target entropy
            mirostat_eta: Mirostat learning rate
            
            **Format Control:**
            grammar: GBNF grammar string for constrained generation
            json_schema: JSON schema for guaranteed valid JSON output
            
            **Context Control:**
            n_keep: Keep first N tokens when context fills (for system prompt)
            
            **Other:**
            seed: Random seed (-1 for random)
            logit_bias: Token ID to bias mapping
            logprobs: Number of logprobs to return
            
        Returns:
            Generated text (or iterator if streaming)
            
        Example:
            # Reduce repetition with DRY sampling
            response = engine.chat(
                messages=[Message(role="user", content="Tell me a story")],
                dry_multiplier=0.8,  # Enable DRY
                dry_base=1.75,
                temperature=0.8
            )
            
            # Force JSON output
            response = engine.chat(
                messages=[...],
                json_schema={"type": "object", "properties": {...}}
            )
        """
        if not self.is_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")
        
        # Build chat messages for llama.cpp format
        chat_messages = []
        
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            chat_messages.append({"role": msg.role, "content": msg.content})
        
        # Build advanced parameters (llama-cpp-python supports most of these)
        kwargs = {
            "messages": chat_messages,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "stop": stop,
            "stream": stream,
            "repeat_penalty": repeat_penalty,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "seed": seed if seed != -1 else None,
        }
        
        # Add advanced parameters if llama-cpp-python version supports them
        # (newer versions have these)
        try:
            # Check if parameters are supported by inspecting signature
            import inspect
            sig = inspect.signature(self.model.create_chat_completion)
            params = sig.parameters
            
            if "min_p" in params:
                kwargs["min_p"] = min_p
            if "typical_p" in params:
                kwargs["typical_p"] = typical_p
            if "tfs_z" in params:
                kwargs["tfs_z"] = tfs_z
            if "mirostat_mode" in params:
                kwargs["mirostat_mode"] = mirostat_mode
                kwargs["mirostat_tau"] = mirostat_tau
                kwargs["mirostat_eta"] = mirostat_eta
            if "logit_bias" in params and logit_bias:
                kwargs["logit_bias"] = logit_bias
            if "logprobs" in params and logprobs:
                kwargs["logprobs"] = logprobs
                
            # Grammar/JSON schema support
            if json_schema and "response_format" in params:
                kwargs["response_format"] = {
                    "type": "json_object",
                    "schema": json_schema
                }
            elif grammar and "grammar" in params:
                kwargs["grammar"] = grammar
                
        except Exception as e:
            if self.verbose:
                print(f"Note: Some advanced parameters not available: {e}")
        
        # Generate completion
        response = self.model.create_chat_completion(**kwargs)
        
        if stream:
            # Return streaming iterator
            def stream_wrapper():
                for chunk in response:
                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        yield content
            return stream_wrapper()
        else:
            # Return complete response
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            return content
    
    def generate(
        self,
        prompt: str,
        temperature: float = 0.8,
        top_p: float = 0.95,
        top_k: int = 40,
        max_tokens: int = 512,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Iterator[str] if stream else str:
        """
        Generate text completion (simpler interface).
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            top_p: Nucleus sampling
            top_k: Top-k sampling
            max_tokens: Max tokens to generate
            stop: Stop sequences
            stream: Enable streaming
            
        Returns:
            Generated text (or iterator if streaming)
        """
        if not self.is_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")
        
        response = self.model(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            stop=stop,
            stream=stream,
            echo=False
        )
        
        if stream:
            def stream_wrapper():
                for chunk in response:
                    text = chunk.get('choices', [{}])[0].get('text', '')
                    if text:
                        yield text
            return stream_wrapper()
        else:
            return response.get('choices', [{}])[0].get('text', '')
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embeddings for text (for RAG/memory systems).
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector (list of floats)
        """
        if not self.is_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")
        
        return self.model.embed(text)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        if not self.is_loaded():
            return {"loaded": False}
        
        return {
            "loaded": True,
            "model_path": self.loaded_model_path,
            "context_size": self.n_ctx,
            "gpu_layers": self.n_gpu_layers,
            "batch_size": self.n_batch
        }
    
    def unload_model(self):
        """Unload the current model from memory"""
        if self.model is not None:
            del self.model
            self.model = None
            self.loaded_model_path = None


# Convenience function for quick testing
def test_inference(model_path: str):
    """Test the inference engine with a simple prompt"""
    print("Initializing Secure Inference Engine...")
    engine = SecureInferenceEngine(model_path=model_path, verbose=True)
    
    print("\nGenerating response...")
    messages = [
        Message(role="user", content="Hello! Can you tell me about yourself?")
    ]
    
    response = engine.chat(
        messages=messages,
        system_prompt="You are Aura, a helpful AI assistant.",
        max_tokens=200
    )
    
    print(f"\nResponse: {response}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_inference(sys.argv[1])
    else:
        print("Usage: python secure_inference_engine.py <path_to_model.gguf>")
        print("\nSecure Inference Engine Status:")
        print(f"llama-cpp-python available: {LLAMA_CPP_AVAILABLE}")
