# Ollama Client Quick Reference

## 🚀 Quick Start

### Basic Usage (Sync)
```python
from ollama_client import OllamaClient, Message

with OllamaClient() as client:
    response = client.chat([
        Message(role='user', content='Hello!')
    ])
    print(response['content'])
```

### Async Usage (For Launchers/UIs)
```python
from ollama_client import AsyncOllamaClient, Message
import asyncio

async def chat():
    async with AsyncOllamaClient() as client:
        response = await client.chat([
            Message(role='user', content='Hello!')
        ])
        print(response['content'])

asyncio.run(chat())
```

---

## 🔧 Common Patterns

### Check if Ollama is Running
```python
from ollama_client import OllamaClient

with OllamaClient() as client:
    if client.health_check():
        print("✅ Ollama is running")
        version = client.get_version()
        print(f"Version: {version}")
    else:
        print("❌ Ollama is not running")
```

### Wait for Ollama to Start
```python
from ollama_client import wait_for_ollama

if wait_for_ollama(max_retries=10, timeout=1.0):
    print("✅ Ollama is ready")
else:
    print("❌ Ollama failed to start")
```

### List Available Models
```python
with OllamaClient() as client:
    models = client.list_models()
    for model in models:
        print(f"- {model}")
```

### Streaming Chat
```python
with OllamaClient() as client:
    for chunk in client.chat_stream([
        Message(role='user', content='Tell me a story')
    ]):
        print(chunk.get('content', ''), end='', flush=True)
```

### Tool Calling
```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
}]

with OllamaClient() as client:
    response = client.chat(
        [Message(role='user', content='What is the weather in Paris?')],
        tools=tools,
        model='llama3.2'
    )
    
    if 'tool_calls' in response:
        for call in response['tool_calls']:
            print(f"Tool: {call['function']['name']}")
            print(f"Args: {call['function']['arguments']}")
```

### Structured Outputs (JSON)
```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "city": {"type": "string"}
    },
    "required": ["name", "age"]
}

with OllamaClient() as client:
    response = client.chat(
        [Message(role='user', content='Extract: John is 30 years old')],
        format=schema
    )
    print(response['content'])  # Valid JSON
```

### Vision/Multimodal
```python
import base64

with open('image.jpg', 'rb') as f:
    image_data = base64.b64encode(f.read()).decode()

with OllamaClient() as client:
    response = client.generate(
        prompt="Describe this image",
        images=[image_data],
        model='llava'
    )
    print(response['response'])
```

---

## 🎯 Launcher Integration

### Health Check Status Widget
```python
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer
from ollama_client import AsyncOllamaClient
import asyncio

class OllamaStatus(QLabel):
    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_status)
        self.timer.start(5000)  # Check every 5 seconds
    
    def check_status(self):
        asyncio.run(self.async_check())
    
    async def async_check(self):
        async with AsyncOllamaClient() as client:
            healthy = await client.health_check()
            if healthy:
                version = await client.get_version()
                self.setText(f"🟢 Ollama {version}")
            else:
                self.setText("🔴 Ollama Offline")
```

### Auto-Start Ollama
```python
import subprocess
from ollama_client import wait_for_ollama

def ensure_ollama():
    with OllamaClient() as client:
        if not client.health_check():
            print("Starting Ollama...")
            subprocess.Popen(['ollama', 'serve'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            
            if wait_for_ollama(max_retries=10):
                print("✅ Ollama started")
                return True
            else:
                print("❌ Failed to start")
                return False
    return True
```

---

## ⚙️ Configuration

### Environment Variables
```bash
# Custom server URL
export OLLAMA_HOST=http://192.168.1.100:11434

# Cloud API key (for ollama.com)
export OLLAMA_API_KEY=your-api-key-here
```

### Custom Timeout
```python
# Short timeout for health checks
client = OllamaClient(timeout=2.0)

# Long timeout for large models
client = OllamaClient(timeout=1200.0)  # 20 minutes
```

### Custom Host
```python
# Local server
client = OllamaClient(host='http://localhost:11434')

# Remote server
client = OllamaClient(host='http://192.168.1.100:11434')

# Cloud API
client = OllamaClient(host='https://ollama.com')
```

---

## 🔴 Error Handling

### Connection Errors
```python
from ollama_client import OllamaClient, ResponseError

try:
    with OllamaClient() as client:
        response = client.chat(messages)
except ConnectionError as e:
    print(f"❌ Cannot connect: {e}")
except ResponseError as e:
    print(f"❌ Server error: {e.error} (HTTP {e.status_code})")
```

### Graceful Degradation
```python
with OllamaClient() as client:
    response = client.chat(messages)
    
    # Client automatically returns error messages, not exceptions
    if response['content'].startswith('[Error:'):
        print("❌ Error:", response['content'])
    else:
        print("✅ Success:", response['content'])
```

---

## 📊 Advanced Features

### Memory Management
```python
# Check loaded models
with OllamaClient() as client:
    running = client.list_running_models()
    for model in running.get('models', []):
        print(f"{model['name']}: {model['size_vram']} VRAM")
    
    # Unload model
    client.unload_model('llama3')
```

### Embeddings (Batch)
```python
with OllamaClient() as client:
    result = client.embed(
        input=["Hello world", "Goodbye world"],
        model='nomic-embed-text'
    )
    
    for i, embedding in enumerate(result['embeddings']):
        print(f"Text {i}: {len(embedding)} dimensions")
```

### Model Copying
```python
with OllamaClient() as client:
    # Copy model
    success = client.copy_model(
        source='llama3',
        destination='llama3-backup'
    )
    
    if success:
        print("✅ Model copied")
```

---

## 🆕 What's New

### ✨ Sync vs Async
- **Sync** (`OllamaClient`): Blocking operations, simple to use
- **Async** (`AsyncOllamaClient`): Non-blocking, for UIs and concurrent code

### ✨ Context Managers
- Automatic cleanup with `with` statement
- No need to manually close connections

### ✨ Better Errors
- `ResponseError` for HTTP errors (with status code)
- `RequestError` for client errors
- Clear connection error messages

### ✨ Health Checks
- Fast `health_check()` method (2-second timeout)
- `wait_for_ollama()` helper for startup detection

### ✨ Environment Support
- `OLLAMA_HOST` for custom servers
- `OLLAMA_API_KEY` for cloud API

---

## 📝 Migration Checklist

- [x] Replace `requests` with `httpx` in requirements.txt
- [x] Use context managers (`with` statement) for new code
- [x] Add health checks to launcher startup
- [x] Use `AsyncOllamaClient` for UI code
- [x] Handle `ResponseError` and `ConnectionError` properly
- [x] Set `OLLAMA_HOST` for custom servers
- [x] Use `wait_for_ollama()` for auto-start detection

---

## 🐛 Troubleshooting

### "Cannot connect to Ollama"
1. Check if Ollama is running: `ollama serve`
2. Check port: default is `11434`
3. Check firewall settings
4. Try: `client.health_check()`

### "Model not found" (404)
1. List available models: `client.list_models()`
2. Pull model: `ollama pull llama3`
3. Verify model name spelling

### "Request timed out"
1. Increase timeout: `OllamaClient(timeout=1200.0)`
2. Check if model is too large for GPU
3. Try smaller model or CPU mode

### Async code not working
1. Must use `async with AsyncOllamaClient()`
2. Must `await` all methods
3. Must run with `asyncio.run()` or in async context

---

## 📚 Documentation

- **Full Upgrade Guide**: `docs/OLLAMA_CLIENT_UPGRADE.md`
- **Harvest Document**: `docs/OLLAMA_PYTHON_HARVEST.md`
- **Test Suite**: `test_upgrades.py`
- **API Coverage**: `docs/COMPLETE_API.md`

---

## 🎉 Key Benefits

- ✅ **100% Backward Compatible** - Old code works unchanged
- ✅ **Async Ready** - Non-blocking UI operations
- ✅ **Context Managers** - Automatic cleanup
- ✅ **Better Errors** - Clear error messages
- ✅ **Health Checks** - Easy service monitoring
- ✅ **Cloud Ready** - API key support
- ✅ **Fully Tested** - Comprehensive test suite
