# Ollama-Python Library Harvest

**Source**: https://github.com/ollama/ollama-python  
**Version**: 0.6.1 (as of harvest)  
**Purpose**: Use patterns for launcher connection logic and improve our client implementation

---

## Key Discoveries for Launcher Connection

### 1. **Context Manager Support (Critical for Launcher)**

The official library implements context managers for automatic resource cleanup:

```python
# Sync version
with Client() as client:
    response = client.chat(...)
# Client closes automatically

# Async version
async with AsyncClient() as client:
    response = await client.chat(...)
# AsyncClient closes automatically
```

**Implementation**:
- Inherits from `contextlib.AbstractContextManager` and `contextlib.AbstractAsyncContextManager`
- `__exit__()` calls `close()` - closes httpx client
- `__aexit__()` calls `await close()` - awaits async close
- Ensures proper cleanup even on exceptions

**Why this matters for launcher**:
- Launcher needs to manage Ollama client lifecycle
- Context managers prevent resource leaks
- Automatic cleanup on shutdown/errors

---

### 2. **Error Handling Pattern**

#### Exception Types:

```python
class RequestError(Exception):
    """Request errors (before sending to server)"""
    def __init__(self, error: str):
        self.error = error

class ResponseError(Exception):
    """Response errors (from server)"""
    def __init__(self, error: str, status_code: int = -1):
        self.error = error
        self.status_code = status_code
```

#### Connection Detection:

```python
CONNECTION_ERROR_MESSAGE = 'Failed to connect to Ollama. Please check that Ollama is downloaded, running and accessible. https://ollama.com/download'

def _request_raw(self, *args, **kwargs):
    try:
        r = self._client.request(*args, **kwargs)
        r.raise_for_status()
        return r
    except httpx.HTTPStatusError as e:
        raise ResponseError(e.response.text, e.response.status_code) from None
    except httpx.ConnectError:
        raise ConnectionError(CONNECTION_ERROR_MESSAGE) from None
```

**Why this matters for launcher**:
- Detect when Ollama service is down
- Distinguish connection vs API errors
- User-friendly error messages
- Launcher can auto-start Ollama on `httpx.ConnectError`

---

### 3. **httpx Over requests**

Official library uses **httpx** instead of **requests**:

**Benefits**:
- Async support (`httpx.AsyncClient`)
- Better timeout handling
- HTTP/2 support
- Connection pooling
- Modern error handling

**Our current implementation**:
- Uses `requests` library (sync only)
- No async support
- Basic error handling

**Migration path**:
```python
# Instead of requests.post()
import httpx

# Sync client
with httpx.Client(timeout=30) as client:
    response = client.post(url, json=data)

# Async client (for launcher)
async with httpx.AsyncClient(timeout=30) as client:
    response = await client.post(url, json=data)
```

---

### 4. **Custom Client Initialization**

```python
class BaseClient:
    def __init__(
        self,
        client,  # httpx.Client or httpx.AsyncClient
        host: Optional[str] = None,
        *,
        follow_redirects: bool = True,
        timeout: Any = None,
        headers: Optional[Mapping[str, str]] = None,
        **kwargs,
    ):
        # Smart host resolution
        if not host:
            host = os.getenv('OLLAMA_HOST') or 'http://127.0.0.1:11434'
        
        # Custom headers
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': f'ollama-python/{__version__} ({platform.machine()} {platform.system().lower()}) Python/{platform.python_version()}',
        }
        
        # API key support (for ollama.com cloud)
        api_key = os.getenv('OLLAMA_API_KEY', None)
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        self._client = client(
            base_url=host,
            follow_redirects=follow_redirects,
            timeout=timeout,
            headers=headers,
            **kwargs  # Pass through to httpx
        )
```

**Why this matters**:
- Launcher can set custom host: `Client(host='http://localhost:11434')`
- Respects `OLLAMA_HOST` environment variable
- Custom timeout: `Client(timeout=60)`
- Cloud API ready with bearer tokens
- httpx kwargs: `Client(verify=False)` for self-signed certs

---

### 5. **Streaming Pattern**

```python
def _request(self, cls: Type[T], *args, stream: bool = False, **kwargs):
    if stream:
        def inner():
            with self._client.stream(*args, **kwargs) as r:
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as e:
                    e.response.read()
                    raise ResponseError(e.response.text, e.response.status_code)
                
                for line in r.iter_lines():
                    part = json.loads(line)
                    if err := part.get('error'):
                        raise ResponseError(err)
                    yield cls(**part)
        
        return inner()
    
    return cls(**self._request_raw(*args, **kwargs).json())
```

**Key insights**:
- Context manager ensures connection cleanup
- Error handling in stream
- JSON per line (NDJSON format)
- Check for inline errors in stream

---

### 6. **AsyncClient Pattern (Critical for Launcher UI)**

```python
class AsyncClient(BaseClient):
    def __init__(self, host: Optional[str] = None, **kwargs):
        super().__init__(httpx.AsyncClient, host, **kwargs)
    
    async def close(self):
        await self._client.aclose()
    
    async def _request_raw(self, *args, **kwargs):
        try:
            r = await self._client.request(*args, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise ResponseError(e.response.text, e.response.status_code)
        except httpx.ConnectError:
            raise ConnectionError(CONNECTION_ERROR_MESSAGE)
    
    async def chat(self, model, messages, stream=False):
        return await self._request(
            ChatResponse,
            'POST',
            '/api/chat',
            json={'model': model, 'messages': messages, 'stream': stream},
            stream=stream,
        )
```

**Why critical for launcher**:
- PySide6 (Qt) UI is single-threaded
- Blocking requests freeze UI
- AsyncClient prevents UI freezing
- Can show progress bars during pulls
- Status updates during generation

---

### 7. **Progress Streaming (Model Pulls)**

```python
# Example from pull.py
from tqdm import tqdm

current_digest, bars = '', {}
for progress in client.pull('gemma3', stream=True):
    digest = progress.get('digest', '')
    
    if digest != current_digest and current_digest in bars:
        bars[current_digest].close()
    
    if not digest:
        print(progress.get('status'))
        continue
    
    if digest not in bars and (total := progress.get('total')):
        bars[digest] = tqdm(
            total=total,
            desc=f'pulling {digest[7:19]}',
            unit='B',
            unit_scale=True
        )
    
    if completed := progress.get('completed'):
        bars[digest].update(completed - bars[digest].n)
    
    current_digest = digest
```

**For launcher**:
- Show download progress when pulling models
- Multiple digest bars for layers
- Status messages (pulling, verifying, writing)
- Completed bytes tracking

---

### 8. **Type Hints and Response Objects**

```python
from ollama import ChatResponse, GenerateResponse, ListResponse

# All responses are typed Pydantic models
response: ChatResponse = client.chat(...)
print(response.message.content)
print(response.message.tool_calls)

# Access like dict or object
print(response['message']['content'])  # dict-style
print(response.message.content)        # object-style
```

**Benefits**:
- IDE autocomplete
- Type checking with mypy
- Proper serialization
- Clear API surface

---

### 9. **Tool Calling Pattern**

```python
def add_numbers(a: int, b: int) -> int:
    '''
    Add two numbers together.
    
    Args:
      a: First number to add
      b: Second number to add
    
    Returns:
      int: The sum of a and b
    '''
    return a + b

# Pass function directly - docstring converted to Tool schema
response = client.chat(
    model='llama3.2',
    messages=[{'role': 'user', 'content': 'What is 5 + 7?'}],
    tools=[add_numbers]  # Function, not dict!
)

if response.message.tool_calls:
    for tc in response.message.tool_calls:
        fn_name = tc.function.name
        args = tc.function.arguments
        # Execute tool
        result = available_tools[fn_name](**args)
        # Send result back
        messages.append({
            'role': 'tool',
            'content': str(result),
            'tool_name': fn_name
        })
```

**Key insights**:
- Pass Python functions directly (Google docstring format)
- Library converts to Ollama Tool schema
- `convert_function_to_tool()` utility
- Simpler than manual schema writing

---

## Recommendations for Launcher

### 1. **Connection Health Check**

```python
class OllamaLauncher:
    def __init__(self):
        self.client = None
    
    async def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get('http://localhost:11434/api/version')
                return r.status_code == 200
        except httpx.ConnectError:
            return False
    
    async def wait_for_ollama(self, max_retries=10):
        """Wait for Ollama to start"""
        for i in range(max_retries):
            if await self.check_ollama():
                return True
            await asyncio.sleep(1)
        return False
```

### 2. **Auto-Start Ollama**

```python
async def ensure_ollama_running(self):
    """Start Ollama if not running"""
    if not await self.check_ollama():
        # Start Ollama service
        subprocess.Popen(['ollama', 'serve'], 
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Wait for it to be ready
        if not await self.wait_for_ollama():
            raise RuntimeError("Failed to start Ollama")
```

### 3. **Async Client for UI**

```python
from ollama import AsyncClient, ResponseError

class AuraLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ollama = AsyncClient()
    
    async def check_models(self):
        """Non-blocking model list"""
        try:
            models = await self.ollama.list()
            self.update_model_list(models)
        except ConnectionError:
            self.show_error("Ollama not running")
        except ResponseError as e:
            self.show_error(f"API error: {e.error}")
    
    def closeEvent(self, event):
        """Clean up on exit"""
        asyncio.run(self.ollama.close())
        event.accept()
```

### 4. **Migrate from requests to httpx**

**Current code**:
```python
import requests

def chat(self, model, messages):
    response = requests.post(
        f"{self.base_url}/api/chat",
        json={'model': model, 'messages': messages}
    )
    return response.json()
```

**New code with httpx**:
```python
import httpx

class OllamaClient:
    def __init__(self, host='http://localhost:11434'):
        self._client = httpx.Client(
            base_url=host,
            timeout=30,
            follow_redirects=True
        )
    
    def chat(self, model, messages):
        try:
            response = self._client.post(
                '/api/chat',
                json={'model': model, 'messages': messages}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ResponseError(e.response.text, e.response.status_code)
        except httpx.ConnectError:
            raise ConnectionError("Ollama not running")
    
    def close(self):
        self._client.close()
```

---

## Additional Features to Adopt

### 1. **Web Search/Fetch Tools** (New!)

```python
from ollama import web_search, web_fetch

# Search the web
results = client.web_search('ollama news', max_results=5)
for result in results.results:
    print(f"{result.title}: {result.url}")

# Fetch page content
page = client.web_fetch('https://ollama.com/blog')
print(page.content)
```

**Requires**: `OLLAMA_API_KEY` env var for ollama.com API

### 2. **"Thinking" Parameter** (Reasoning models)

```python
response = client.chat(
    model='qwen3',
    messages=[...],
    think=True,  # or 'low', 'medium', 'high'
)

if response.message.thinking:
    print("Model's reasoning:")
    print(response.message.thinking)

print("Final answer:")
print(response.message.content)
```

### 3. **Log Probabilities**

```python
response = client.chat(
    model='llama3.2',
    messages=[...],
    logprobs=True,
    top_logprobs=5,  # Top 5 token probabilities
)

# Access logprobs in response
```

### 4. **Blob Upload for Model Creation**

```python
# Upload model file
digest = client.create_blob('path/to/model.gguf')

# Create model from blob
client.create(
    'my-model',
    files={'model.gguf': digest}
)
```

---

## Migration Checklist

- [ ] Replace `requests` with `httpx` in `src/ollama_client.py`
- [ ] Add `AsyncClient` support for launcher UI
- [ ] Implement context manager (`__enter__`, `__exit__`)
- [ ] Add proper error types (`ResponseError`, `RequestError`)
- [ ] Improve connection detection (`httpx.ConnectError`)
- [ ] Add `OLLAMA_HOST` environment variable support
- [ ] Add timeout configuration
- [ ] Implement health check method
- [ ] Add auto-start Ollama capability
- [ ] Use progress streaming for model pulls
- [ ] Adopt Pydantic response types
- [ ] Support cloud API with bearer tokens
- [ ] Add web_search/web_fetch capabilities
- [ ] Support "think" parameter for reasoning models
- [ ] Add logprobs support

---

## Code Examples

### Launcher Health Check Integration

```python
import asyncio
import httpx
from PySide6.QtWidgets import QLabel, QPushButton

class OllamaStatusWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.status_label = QLabel("Checking Ollama...")
        self.start_button = QPushButton("Start Ollama")
        self.start_button.clicked.connect(self.start_ollama)
        
        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)
        self.setLayout(layout)
        
        # Check status every 5 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_status)
        self.timer.start(5000)
    
    async def check_ollama(self):
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get('http://localhost:11434/api/version')
                return r.status_code == 200
        except:
            return False
    
    def check_status(self):
        asyncio.run(self._check_status_impl())
    
    async def _check_status_impl(self):
        if await self.check_ollama():
            self.status_label.setText("🟢 Ollama Running")
            self.start_button.setEnabled(False)
        else:
            self.status_label.setText("🔴 Ollama Stopped")
            self.start_button.setEnabled(True)
    
    def start_ollama(self):
        import subprocess
        subprocess.Popen(['ollama', 'serve'])
```

### Async Chat Implementation

```python
from ollama import AsyncClient, ResponseError

async def chat_with_async(model: str, message: str):
    async with AsyncClient() as client:
        try:
            response = await client.chat(
                model=model,
                messages=[{'role': 'user', 'content': message}]
            )
            return response.message.content
        except ConnectionError:
            return "Error: Ollama is not running"
        except ResponseError as e:
            return f"Error: {e.error} (status {e.status_code})"
```

### Progress Bar for Model Pull

```python
from PySide6.QtWidgets import QProgressBar
from ollama import Client

class ModelDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.progress_bar = QProgressBar()
        layout = QVBoxLayout()
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)
    
    def download_model(self, model_name: str):
        client = Client()
        
        for progress in client.pull(model_name, stream=True):
            if progress.get('total'):
                completed = progress.get('completed', 0)
                total = progress['total']
                percent = int((completed / total) * 100)
                self.progress_bar.setValue(percent)
            
            status = progress.get('status')
            self.progress_bar.setFormat(status or '')
```

---

## Summary

**Top 3 Priorities for Launcher**:

1. **AsyncClient** - Prevents UI freezing during API calls
2. **Error Handling** - Detect when Ollama is down, auto-start if needed
3. **Context Managers** - Proper resource cleanup on exit

**Migration Benefits**:
- Non-blocking launcher UI
- Automatic service health monitoring
- Better error messages
- Cloud API ready
- Modern async/await patterns
- Type-safe responses

**Next Steps**:
1. Create async version of OllamaClient using httpx.AsyncClient
2. Add health check to launcher startup
3. Implement auto-start logic
4. Add status indicator to launcher UI
5. Test with launcher lifecycle (start, stop, restart)
