"""Ollama client for AuraNexus projects.

Upgraded with httpx, async support, and context managers based on official ollama-python patterns.
"""

import contextlib
import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Iterator, AsyncIterator, Union, Any
import httpx


# ============================================================================
# Exception Classes
# ============================================================================

class RequestError(Exception):
    """Error raised before sending request to server."""
    
    def __init__(self, error: str):
        super().__init__(error)
        self.error = error


class ResponseError(Exception):
    """Error raised from server response."""
    
    def __init__(self, error: str, status_code: int = -1):
        # Try to parse JSON error message
        try:
            error_dict = json.loads(error)
            error = error_dict.get('error', error)
        except (json.JSONDecodeError, AttributeError):
            pass
        
        super().__init__(error)
        self.error = error
        self.status_code = status_code
    
    def __str__(self) -> str:
        return f'{self.error} (status code: {self.status_code})'


# Connection error message
CONNECTION_ERROR_MESSAGE = (
    'Failed to connect to Ollama. Please check that Ollama is downloaded, '
    'running and accessible. https://ollama.com/download'
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Message:
    """Chat message structure with timestamp."""
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None  # For tool calling responses
    tool_name: Optional[str] = None  # For tool results
    timestamp: datetime = field(default_factory=datetime.now)  # Auto-generated timestamp
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        d = {
            'role': self.role,
            'content': self.content
        }
        if self.tool_calls:
            d['tool_calls'] = self.tool_calls
        if self.tool_name:
            d['tool_name'] = self.tool_name
        if self.timestamp:
            d['timestamp'] = self.timestamp.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Message':
        """Create Message from dictionary."""
        timestamp = d.get('timestamp')
        if timestamp and isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif not timestamp:
            timestamp = datetime.now()
        
        return cls(
            role=d['role'],
            content=d['content'],
            tool_calls=d.get('tool_calls'),
            tool_name=d.get('tool_name'),
            timestamp=timestamp
        )


# ============================================================================
# Base Client (Shared Logic)
# ============================================================================

class BaseClient(contextlib.AbstractContextManager, contextlib.AbstractAsyncContextManager):
    """Base client with shared initialization logic."""
    
    def __init__(
        self,
        client_class,
        host: Optional[str] = None,
        *,
        follow_redirects: bool = True,
        timeout: Any = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """Initialize base client with httpx.
        
        Args:
            client_class: httpx.Client or httpx.AsyncClient
            host: Ollama server URL (default: OLLAMA_HOST env or http://localhost:11434)
            follow_redirects: Follow HTTP redirects
            timeout: Request timeout (default: None = no timeout)
            headers: Custom headers
            **kwargs: Additional httpx client arguments
        """
        # Resolve host
        if not host:
            host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        self.base_url = host.rstrip('/')
        
        # Build headers
        default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': f'auranexus-ollama/1.0 ({platform.machine()} {platform.system().lower()}) Python/{platform.python_version()}',
        }
        
        # Add API key if present (for cloud ollama.com API)
        api_key = os.getenv('OLLAMA_API_KEY')
        if api_key:
            default_headers['Authorization'] = f'Bearer {api_key}'
        
        # Merge custom headers
        if headers:
            default_headers.update({k.lower(): v for k, v in headers.items() if v is not None})
        
        # Create httpx client
        self._client = client_class(
            base_url=self.base_url,
            follow_redirects=follow_redirects,
            timeout=timeout,
            headers=default_headers,
            **kwargs
        )
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        self.close()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()
    
    def close(self):
        """Close sync client (implemented by subclass)."""
        raise NotImplementedError
    
    async def aclose(self):
        """Close async client (implemented by subclass)."""
        raise NotImplementedError


# ============================================================================
# Sync Client
# ============================================================================

class OllamaClient(BaseClient):
    """Synchronous client for communicating with Ollama API.
    
    Uses httpx for better error handling and connection management.
    Supports context manager for automatic cleanup.
    
    Example:
        with OllamaClient() as client:
            response = client.chat([Message(role='user', content='Hello')])
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        model: str = "llama3",
        timeout: float = 600.0,
        **kwargs
    ) -> None:
        """Initialize Ollama client.
        
        Args:
            host: Ollama server URL (default: from OLLAMA_HOST env or http://localhost:11434)
            model: Default model to use
            timeout: Request timeout in seconds (default: 600)
            **kwargs: Additional httpx.Client arguments
        """
        super().__init__(httpx.Client, host, timeout=timeout, **kwargs)
        self.model = model
        
        # Auto-select first available model if default doesn't exist
        try:
            available = self.list_models()
            if available and model not in available:
                self.model = available[0]
        except Exception:
            pass  # Silently fail if can't connect yet
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    async def aclose(self):
        """Async close (not used for sync client, but required by base)."""
        self.close()
    
    def _request_raw(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make raw HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx
            
        Returns:
            httpx.Response object
            
        Raises:
            ResponseError: On HTTP error status
            ConnectionError: On connection failure
        """
        try:
            r = self._client.request(method, url, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise ResponseError(e.response.text, e.response.status_code) from None
        except httpx.ConnectError:
            raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None
    
    def health_check(self) -> bool:
        """Check if Ollama server is running and accessible.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            r = self._client.get('/api/version', timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def chat(self, messages: List[Message], system_prompt: Optional[str] = None, 
             options: Optional[Dict] = None, model: Optional[str] = None,
             format: Optional[Dict] = None, tools: Optional[List[Dict]] = None) -> Dict:
        """Send chat request to Ollama and return response.
        
        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt
            options: Model parameters (temperature, top_k, etc.)
            model: Model name to use
            format: JSON schema for structured outputs (dict with 'type', 'properties', etc.)
            tools: List of tool definitions for function calling
            
        Returns:
            Dict with 'content' (str) and optionally 'tool_calls' (list)
            
        Raises:
            ResponseError: On HTTP error
            ConnectionError: On connection failure
        """
        msg_list = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_name:
                msg_dict["tool_name"] = m.tool_name
            msg_list.append(msg_dict)
        
        if system_prompt:
            msg_list = [{"role": "system", "content": system_prompt}] + msg_list
        
        payload: Dict = {
            "model": (model or self.model),
            "stream": False,
            "messages": msg_list,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        if options and isinstance(options, dict):
            payload["options"] = options
        if format:
            payload["format"] = format
        if tools:
            payload["tools"] = tools
        
        try:
            resp = self._request_raw('POST', '/api/chat', json=payload)
            data = resp.json()
            
            msg = data.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            
            # Return structured response
            result = {"content": content}
            if tool_calls:
                result["tool_calls"] = tool_calls
            
            # Check if content is empty and no tool calls
            if (not content or not content.strip()) and not tool_calls:
                result["content"] = "[Error: Model returned empty response. Try a different model or restart Ollama.]"
            
            return result
        except ConnectionError:
            return {"content": "[Error: Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)]"}
        except httpx.TimeoutException:
            return {"content": "[Error: Request timed out. The model may be too slow or unresponsive.]"}
        except ResponseError as e:
            if e.status_code == 404:
                available = self.list_models()
                if available:
                    models_str = ", ".join(available[:5])
                    return {"content": f"[Error: Model '{model or self.model}' not found. Available models: {models_str}]"}
                return {"content": f"[Error: Model '{model or self.model}' not found. Use 'ollama pull {model or self.model}' to download it.]"}
            elif e.status_code == 500:
                return {"content": "[Error: Ollama server error. Try restarting Ollama or using a different model.]"}
            return {"content": f"[Error: HTTP {e.status_code} - {e.error}]"}
        except Exception as e:
            return {"content": f"[Error: {type(e).__name__}: {e}]"}
    
    def chat_stream(self, messages: List[Message], system_prompt: Optional[str] = None,
                    options: Optional[Dict] = None, model: Optional[str] = None,
                    format: Optional[Dict] = None, tools: Optional[List[Dict]] = None):
        """Stream chat responses from Ollama token by token.
        
        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt
            options: Model parameters (temperature, top_k, etc.)
            model: Model name to use
            format: JSON schema for structured outputs
            tools: List of tool definitions for function calling
            
        Yields:
            Dict with 'content' (str) and optionally 'tool_calls' (list) in final message
        """
        msg_list = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_name:
                msg_dict["tool_name"] = m.tool_name
            msg_list.append(msg_dict)
        
        if system_prompt:
            msg_list = [{"role": "system", "content": system_prompt}] + msg_list
        
        payload: Dict = {
            "model": (model or self.model),
            "stream": True,
            "messages": msg_list,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        if options and isinstance(options, dict):
            payload["options"] = options
        if format:
            payload["format"] = format
        if tools:
            payload["tools"] = tools
        
        try:
            with self._client.stream('POST', '/api/chat', json=payload) as resp:
                resp.raise_for_status()
                
                tool_calls_buffer = []
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                msg = data["message"]
                                content = msg.get("content", "")
                                if content:
                                    yield {"content": content}
                                
                                # Accumulate tool calls
                                if "tool_calls" in msg:
                                    tool_calls_buffer.extend(msg["tool_calls"])
                            
                            # On final message, include tool_calls if present
                            if data.get("done", False) and tool_calls_buffer:
                                yield {"content": "", "tool_calls": tool_calls_buffer, "done": True}
                                break
                            elif data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except ConnectionError:
            yield {"content": "[Error: Cannot connect to Ollama]"}
        except httpx.TimeoutException:
            yield {"content": "[Error: Request timed out]"}
        except ResponseError as e:
            yield {"content": f"[Error: {e.error}]"}
        except Exception as e:
            yield {"content": f"[Error: {e}]"}
    
    def pull_model(self, model_name: str):
        """Download a model from Ollama library."""
        payload = {"model": model_name, "stream": True}
        
        try:
            with self._client.stream('POST', '/api/pull', json=payload) as resp:
                resp.raise_for_status()
                
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            if status:
                                yield status
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"Error: {e}"
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a model from local storage."""
        try:
            resp = self._request_raw('DELETE', '/api/delete', json={"model": model_name})
            return True
        except Exception:
            return False
    
    def show_model(self, model_name: str) -> Optional[Dict]:
        """Get detailed information about a model."""
        try:
            resp = self._request_raw('POST', '/api/show', json={"model": model_name})
            return resp.json()
        except Exception:
            return None
    
    def list_models(self) -> List[str]:
        """Get list of available Ollama models."""
        try:
            resp = self._client.get('/api/tags', timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            return []
    
    def create_from_modelfile(self, model_name: str, modelfile_content: str):
        """Create a model from a Modelfile (for importing existing models)."""
        payload = {
            "model": model_name,
            "modelfile": modelfile_content,
            "stream": True
        }
        
        print(f"DEBUG [OllamaClient]: Sending create request to {self.base_url}/api/create")
        print(f"DEBUG [OllamaClient]: Payload: {payload}")
        
        try:
            with self._client.stream('POST', '/api/create', json=payload) as resp:
                # Check for HTTP errors before processing stream
                if resp.status_code >= 400:
                    error_text = resp.text
                    print(f"DEBUG [OllamaClient]: HTTP {resp.status_code} error: {error_text}")
                    yield f"Error: HTTP {resp.status_code} - {error_text}"
                    return
                
                resp.raise_for_status()
                
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            if status:
                                yield status
                            # Check for errors in the response
                            if "error" in data:
                                error_msg = data.get("error", "Unknown error")
                                print(f"DEBUG [OllamaClient]: Error in response: {error_msg}")
                                yield f"Error: {error_msg}"
                                return
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError as je:
                            print(f"DEBUG [OllamaClient]: JSON decode error: {je}")
                            continue
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error: {e}"
            print(f"DEBUG [OllamaClient]: {error_msg}")
            yield f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"DEBUG [OllamaClient]: {error_msg}")
            yield f"Error: {error_msg}"
    
    def embed(self, input: str | List[str], model: Optional[str] = None, 
              keep_alive: Optional[str] = None, options: Optional[Dict] = None) -> Dict:
        """Generate embeddings using the /api/embed endpoint (batch support).
        
        Args:
            input: Text string or list of strings to embed
            model: Embedding model to use (default: current model)
            keep_alive: How long to keep model in memory (e.g., "5m", "1h", "0" to unload)
            options: Additional model parameters
            
        Returns:
            Dict with 'embeddings' (list of lists of floats) and 'model' (str)
            For single input, returns one embedding. For batch, returns multiple.
        """
        payload = {
            "model": model or self.model,
            "input": input
        }
        
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        if options:
            payload["options"] = options
        
        try:
            resp = self._request_raw('POST', '/api/embed', json=payload)
            return resp.json()
        except ResponseError as e:
            return {"error": f"Embedding request failed: {e.error}"}
        except Exception as e:
            return {"error": f"Embedding request failed: {e}"}
    
    def list_running_models(self) -> Dict:
        """Get list of currently loaded models with memory usage (/api/ps).
        
        Returns:
            Dict with 'models' key containing list of loaded models.
            Each model has: name, model, size, digest, expires_at, size_vram
        """
        try:
            resp = self._client.get('/api/ps', timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": f"Failed to get running models: {e}", "models": []}
    
    def unload_model(self, model_name: Optional[str] = None) -> bool:
        """Unload a model from memory immediately.
        
        Args:
            model_name: Model to unload (default: current model)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Send a generate request with keep_alive=0 to unload
            payload = {
                "model": model_name or self.model,
                "keep_alive": 0
            }
            resp = self._request_raw('POST', '/api/generate', json=payload)
            return True
        except Exception:
            return False

    def generate(self, prompt: str, system: Optional[str] = None, 
                 images: Optional[List[str]] = None, suffix: Optional[str] = None,
                 model: Optional[str] = None, options: Optional[Dict] = None,
                 format: Optional[Dict] = None, keep_alive: Optional[str] = None) -> Dict:
        """Generate completion using /api/generate endpoint.
        
        Useful for code completion, text generation, and vision models.
        
        Args:
            prompt: The prompt to generate from
            system: System prompt override
            images: List of base64-encoded images (for multimodal models)
            suffix: Text after the completion (for fill-in-the-middle code completion)
            model: Model override
            options: Model parameters
            format: JSON schema for structured outputs
            keep_alive: How long to keep model in memory
            
        Returns:
            Dict with 'response' (str), 'context' (list), and metadata
        """
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False
        }
        
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images
        if suffix:
            payload["suffix"] = suffix
        if options:
            payload["options"] = options
        if format:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        
        try:
            resp = self._request_raw('POST', '/api/generate', json=payload)
            return resp.json()
        except ResponseError as e:
            return {"error": f"Generation failed: {e.error}", "response": ""}
        except Exception as e:
            return {"error": f"Generation failed: {e}", "response": ""}
    
    def generate_stream(self, prompt: str, system: Optional[str] = None,
                       images: Optional[List[str]] = None, suffix: Optional[str] = None,
                       model: Optional[str] = None, options: Optional[Dict] = None,
                       format: Optional[Dict] = None, keep_alive: Optional[str] = None):
        """Stream generation using /api/generate endpoint.
        
        Yields response chunks as they arrive.
        """
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": True
        }
        
        if system:
            payload["system"] = system
        if images:
            payload["images"] = images
        if suffix:
            payload["suffix"] = suffix
        if options:
            payload["options"] = options
        if format:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        
        try:
            with self._client.stream('POST', '/api/generate', json=payload) as resp:
                resp.raise_for_status()
                
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            yield data
                        except json.JSONDecodeError:
                            continue
        except ResponseError as e:
            yield {"error": str(e.error), "done": True}
        except Exception as e:
            yield {"error": str(e), "done": True}
    
    def copy_model(self, source: str, destination: str) -> bool:
        """Copy a model to a new name.
        
        Args:
            source: Source model name
            destination: Destination model name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._request_raw('POST', '/api/copy', json={"source": source, "destination": destination})
            return True
        except Exception:
            return False
    
    def get_version(self) -> Optional[str]:
        """Get Ollama server version.
        
        Returns:
            Version string (e.g., "0.5.1") or None if unavailable
        """
        try:
            resp = self._client.get('/api/version', timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("version")
        except Exception:
            return None


# ============================================================================
# Async Client
# ============================================================================

class AsyncOllamaClient(BaseClient):
    """Asynchronous client for non-blocking Ollama API calls.
    
    Critical for launcher UI to prevent freezing during long operations.
    Uses httpx.AsyncClient for true async/await support.
    
    Example:
        async with AsyncOllamaClient() as client:
            response = await client.chat([Message(role='user', content='Hello')])
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        model: str = "llama3",
        timeout: float = 600.0,
        **kwargs
    ) -> None:
        """Initialize async Ollama client.
        
        Args:
            host: Ollama server URL (default: from OLLAMA_HOST env or http://localhost:11434)
            model: Default model to use
            timeout: Request timeout in seconds (default: 600)
            **kwargs: Additional httpx.AsyncClient arguments
        """
        super().__init__(httpx.AsyncClient, host, timeout=timeout, **kwargs)
        self.model = model
    
    async def close(self):
        """Close the async HTTP client (not used, see aclose)."""
        await self._client.aclose()
    
    async def aclose(self):
        """Close the async HTTP client."""
        await self._client.aclose()
    
    async def _request_raw(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make async raw HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx
            
        Returns:
            httpx.Response object
            
        Raises:
            ResponseError: On HTTP error status
            ConnectionError: On connection failure
        """
        try:
            r = await self._client.request(method, url, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise ResponseError(e.response.text, e.response.status_code) from None
        except httpx.ConnectError:
            raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None
    
    async def health_check(self) -> bool:
        """Check if Ollama server is running and accessible (async).
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            r = await self._client.get('/api/version', timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False
    
    async def list_models(self) -> List[str]:
        """Get list of available Ollama models (async)."""
        try:
            resp = await self._client.get('/api/tags', timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            return []
    
    async def chat(self, messages: List[Message], system_prompt: Optional[str] = None,
                   options: Optional[Dict] = None, model: Optional[str] = None,
                   format: Optional[Dict] = None, tools: Optional[List[Dict]] = None) -> Dict:
        """Send async chat request to Ollama.
        
        Args:
            messages: List of Message objects
            system_prompt: Optional system prompt
            options: Model parameters
            model: Model name to use
            format: JSON schema for structured outputs
            tools: List of tool definitions
            
        Returns:
            Dict with 'content' and optionally 'tool_calls'
        """
        msg_list = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            if m.tool_name:
                msg_dict["tool_name"] = m.tool_name
            msg_list.append(msg_dict)
        
        if system_prompt:
            msg_list = [{"role": "system", "content": system_prompt}] + msg_list
        
        payload = {
            "model": (model or self.model),
            "stream": False,
            "messages": msg_list,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options
        if format:
            payload["format"] = format
        if tools:
            payload["tools"] = tools
        
        try:
            resp = await self._request_raw('POST', '/api/chat', json=payload)
            data = resp.json()
            
            msg = data.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            
            result = {"content": content}
            if tool_calls:
                result["tool_calls"] = tool_calls
            
            if (not content or not content.strip()) and not tool_calls:
                result["content"] = "[Error: Model returned empty response]"
            
            return result
        except ConnectionError:
            return {"content": "[Error: Cannot connect to Ollama]"}
        except httpx.TimeoutException:
            return {"content": "[Error: Request timed out]"}
        except ResponseError as e:
            return {"content": f"[Error: HTTP {e.status_code} - {e.error}]"}
        except Exception as e:
            return {"content": f"[Error: {type(e).__name__}: {e}]"}
    
    async def get_version(self) -> Optional[str]:
        """Get Ollama server version (async)."""
        try:
            resp = await self._client.get('/api/version', timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("version")
        except Exception:
            return None


# ============================================================================
# Helper Functions
# ============================================================================

def wait_for_ollama(host: str = "http://localhost:11434", max_retries: int = 10, timeout: float = 1.0) -> bool:
    """Wait for Ollama service to become available (sync).
    
    Args:
        host: Ollama server URL
        max_retries: Maximum number of connection attempts
        timeout: Time between retries in seconds
        
    Returns:
        True if Ollama is available, False if timeout
    """
    import time
    
    client = OllamaClient(host=host, timeout=2.0)
    for i in range(max_retries):
        if client.health_check():
            client.close()
            return True
        time.sleep(timeout)
    
    client.close()
    return False


async def async_wait_for_ollama(host: str = "http://localhost:11434", max_retries: int = 10, timeout: float = 1.0) -> bool:
    """Wait for Ollama service to become available (async).
    
    Args:
        host: Ollama server URL
        max_retries: Maximum number of connection attempts
        timeout: Time between retries in seconds
        
    Returns:
        True if Ollama is available, False if timeout
    """
    import asyncio
    
    async with AsyncOllamaClient(host=host, timeout=2.0) as client:
        for i in range(max_retries):
            if await client.health_check():
                return True
            await asyncio.sleep(timeout)
    
    return False
