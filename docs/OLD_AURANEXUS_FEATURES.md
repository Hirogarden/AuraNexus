# Old AuraNexus Features to Salvage

## Located at: D:\AuraNexus

### ✅ Already Had In-Process LLM Support!

**LlamaCppClient Class** (aura_nexus_app.py lines ~212-273)
- Already implemented llama-cpp-python wrapper
- Methods: `chat()`, `close()`
- Parameters: model_path, n_ctx, n_threads
- Simple text-based chat interface (not using Messages API like we do now)

### 🎯 Key Features to Port

#### 1. **VTube Studio Integration** (avatar/vts_controller.py)
- WebSocket connection to VTube Studio (localhost:8001)
- `set_parameter(name, value)` - Control Live2D parameters
- `test_emote()` - Trigger facial expressions
- Parameters: MouthOpen, EyeSmile, etc.
- **Use Case:** Aura avatar reacts to conversation

#### 2. **Advanced Model Controls**
From UI (lines ~400-550):
- ✅ **n_ctx spinner** (512-32768) - Context window
- ✅ **n_threads spinner** (1-256) - CPU threads  
- ✅ **num_predict spinner** (16-4096) - Max tokens
- **Local GGUF checkbox** - Toggle between Ollama/Local
- **Browse button** - File picker for GGUF models
- **Load button** - Load selected model
- **Scan button** - Scan directory for models
- **Import to Ollama** - Convert GGUF to Ollama model

#### 3. **AnythingLLM RAG Integration**
- **Enable checkbox** - Toggle RAG
- **Mode dropdown**: "Augment (RAG)" or "Responder"
- **Base URL field**: API endpoint (default: http://localhost:3001)
- **API Key field**: Secured input
- **Workspace field**: AnythingLLM workspace name
- **Log history checkbox**: Save chat to AnythingLLM
- **Log target dropdown**: "Documents" or "Chat History"

#### 4. **Voice/TTS Features**
- **Voice toggle button** - Enable/disable TTS
- **speak_async()** method integration
- pyttsx3 library used

#### 5. **UI Controls**
- **Target Length spinner** (1-20) - Target sentences for responses
- **Allow overflow checkbox** - Let responses exceed target
- **Enter Sends checkbox** - Enter key behavior
- **Auto Intro checkbox** - Automatic greeting
- **Assistant name field** - Customize AI name (default: "Aura")
- **User name field** - Customize user name (default: "You")

#### 6. **Model Health & Testing**
- **Health button** - Check Ollama/model status
- **Test Chat button** - Quick model test
- **Latency label** - Show response time
- **Model refresh button** - Reload available models

#### 7. **Diagnostics & Logging**
Tools directory:
- **health_check.py** - Verify all imports work
- **diagnose_ollama.py** - Debug Ollama issues
- **stress_ollama.py** - Load testing
- **test_model_change.py** - Model switching tests

Logging system:
- logs/ollama_requests.log
- Detailed request/response logging
- Error tracking with timestamps

#### 8. **Smart Error Handling**
OllamaClient had sophisticated error handling:
- **Model fallback** - Auto-switch on 500 errors
- **Retry logic** - 2 attempts with 0.2s delay
- **404 detection** - "Model not found" message
- **Network error logging** - Detailed diagnostics
- **Model availability check** - Query /api/tags for alternatives

#### 9. **File Drop Support**
- `FileDropLineEdit` class - Drag & drop GGUF files
- Integrated with local model path input

### 📦 Libraries Used (from health_check.py)
- PySide6 ✅ (we have)
- requests ✅ (we have)
- pyttsx3 ❌ (TTS - need to add)
- websocket ❌ (VTube Studio - need to add)

### 🔧 Implementation Priority

**High Priority:**
1. ✅ **Port n_ctx/n_threads controls** - Already added context_size_spin
2. **Add model scanning** - Auto-detect GGUF files in directory
3. **Add health check button** - Test model before use
4. **Add latency display** - Show inference time

**Medium Priority:**
1. **AnythingLLM RAG integration** - Add as optional feature
2. **Model import to Ollama** - Convert GGUF → Ollama (if we add Ollama back)
3. **Target length control** - Smart response length management
4. **Auto intro** - Greeting on startup

**Low Priority (Optional):**
1. **VTube Studio integration** - Live2D avatar control
2. **TTS voice output** - pyttsx3 integration
3. **File drag & drop** - For model loading
4. **Assistant/User name customization** - Personalization

### 💡 New Ideas from Old Code

1. **Model Fallback System** - If a model fails, auto-switch to a working one
2. **Request Logging** - Keep detailed logs for debugging
3. **Health Monitoring** - Continuous background checks
4. **Workspace Management** - Multiple conversation contexts
5. **Smart Retry Logic** - Handle transient errors gracefully

### 🚫 What NOT to Port

- Ollama-specific code (we're in-process now)
- Docker integration (removed for security)
- HTTP request logic (no external services)
- Complex fallback for Ollama 500 errors (not applicable)

---

## Next Steps

1. Add model scanning feature to unified_chat_window.py
2. Add health check/test button
3. Show inference latency in status bar
4. Consider AnythingLLM RAG as optional plugin
5. Evaluate VTube Studio integration for fun/demos
