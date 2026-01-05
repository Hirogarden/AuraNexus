"""LLM Model Manager - Handles llama.cpp integration and inference."""

import os
from pathlib import Path
from typing import Optional, Generator
from llama_cpp import Llama


class ModelManager:
    """Manages the Mistral 7B model and inference."""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize the model manager.
        
        Args:
            model_path: Path to the GGUF model file. If None, uses default.
        """
        self.model_path = model_path or self._get_default_model_path()
        self.llm: Optional[Llama] = None
        self.loaded = False
        
    def _get_default_model_path(self) -> str:
        """Get the default model path."""
        # Models are stored in the ./models directory
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True)
        
        # Look for Mistral 7B GGUF
        mistral_name = "mistral-7b-instruct-v0.1.Q4_K_M.gguf"
        return str(model_dir / mistral_name)
    
    def load_model(self) -> bool:
        """Load the language model.
        
        Returns:
            True if model loaded successfully, False otherwise.
        """
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Model not found at {self.model_path}\n"
                    "Please download Mistral 7B GGUF from HuggingFace"
                )
            
            # Load with optimized settings
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,  # Context window
                n_threads=os.cpu_count() or 4,
                n_gpu_layers=0,  # Set to >0 if you have CUDA support
                verbose=False,
            )
            self.loaded = True
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            self.loaded = False
            return False
    
    def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """Generate a chat response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        if not self.loaded or self.llm is None:
            return "Error: Model not loaded. Please check model file."
        
        try:
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def stream_chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 512) -> Generator[str, None, None]:
        """Stream a chat response token by token.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            
        Yields:
            Response tokens as they are generated
        """
        if not self.loaded or self.llm is None:
            yield "Error: Model not loaded. Please check model file."
            return
        
        try:
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            for chunk in response:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
        except Exception as e:
            yield f"Error generating response: {str(e)}"
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.loaded and self.llm is not None
    
    def unload_model(self) -> None:
        """Unload the model to free memory."""
        self.llm = None
        self.loaded = False
