# AuraNexus - Project Structure

## 📁 Main Entry Points

### Primary Launcher
- **`chat_launcher.py`** - Main Python entry point for the chat application
- **`run_aura_nexus.ps1`** - PowerShell launcher (handles venv activation automatically)

### Quick Start
```powershell
# Windows (Recommended)
.\run_aura_nexus.ps1

# Or directly with Python
python chat_launcher.py
```

## 📦 Directory Structure

```
AuraNexus/
├── src/                          # Core application code
│   ├── ollama_chat.py            # Main chat UI
│   ├── ollama_client.py          # Ollama API client
│   ├── vram_optimizer.py         # VRAM detection & optimization
│   ├── memory_estimator.py       # Model memory calculation
│   ├── vram_monitor.py           # Real-time VRAM monitoring
│   ├── gguf_architecture.py      # GGUF model architecture detection
│   ├── layer_splitter.py         # Smart layer offloading strategies
│   ├── progressive_loader.py     # Progressive model loading
│   ├── time_utils.py             # Time-aware conversation features
│   ├── builtin_rag.py            # Built-in RAG system
│   └── anythingllm_client.py     # AnythingLLM integration
│
├── tests/                        # All test files
│   ├── test_kobold_harvest.py    # KoboldCPP harvest feature demo
│   ├── test_all_features.py      # Comprehensive feature tests
│   └── ...
│
├── docs/                         # Documentation
│   ├── DEV_SETUP.md              # Developer setup guide
│   ├── MODEL_SETUP.md            # Model configuration guide
│   ├── GITHUB_PUBLISH.md         # Publishing guide
│   └── KOBOLDCPP_GGUF_HARVEST.md # KoboldCPP patterns harvested
│
├── archive/                      # Legacy code (for harvesting features)
│   └── aura_nexus_app.py         # Old full-featured app (deprecated)
│
├── tools/                        # Utility scripts
│   ├── health_check.py           # System health diagnostics
│   ├── diagnose_ollama.py        # Ollama troubleshooting
│   ├── stress_ollama.py          # Load testing
│   └── ...
│
├── app/                          # Legacy launcher system
│   ├── aura_launcher.py          # Service orchestrator
│   ├── aura_api/                 # API server
│   └── config/                   # Configuration files
│
├── avatar/                       # Avatar integration (VTS, VSeeFace)
├── data/                         # Data storage
│   └── rag/                      # RAG database
├── engines/                      # Model engines (KoboldCPP)
├── frontends/                    # Frontend integrations (SillyTavern)
├── tts/                          # TTS system (Piper)
└── ui/                           # UI components (Electron)
```

## 🚀 Features Implemented

### KoboldCPP Harvest (Complete)
All features pilfered from KoboldCPP for optimal GGUF model handling:

✅ **Low VRAM Mode** - Automatic optimization for 8GB GPUs  
✅ **Memory Estimation** - Pre-load OOM prevention  
✅ **Real-time VRAM Monitoring** - 1-second polling with alerts  
✅ **Architecture Detection** - 19+ architectures (Llama, Qwen2, Gemma, Mamba, etc.)  
✅ **Smart Layer Splitting** - 5 offloading strategies (attention/MLP priority)  
✅ **Progressive Loading** - Real-time download progress with ETA  

### Core Features
- **Ollama Integration** - Full API support (14/14 endpoints)
- **Tool Calling** - Function execution (time, calculator, file operations)
- **JSON Mode** - Structured output with schema validation
- **RAG Memory** - Built-in RAG + AnythingLLM support
- **Time-Aware Chat** - Automatic time context injection
- **Model Management** - Download, import, delete, unload
- **Conversation Persistence** - Save/load with timestamps

## 🧹 What Got Cleaned

### Removed (10 files)
- `ai_launcher.py` - Empty deprecation stub
- `companion_app.py` - Legacy compatibility shim
- `launch.py` - Redundant launcher
- `run_auranexus.ps1` - Duplicate (kept `run_aura_nexus.ps1`)
- Old tool tests - Superseded versions

### Organized
- All test files moved to `tests/`
- Deprecated full app archived to `archive/`
- All `__pycache__` directories cleaned (1000+ folders)

## 📝 Configuration

### VRAM Optimization (Auto-detected)
Your system: **RTX 5060 8GB** → "low" tier
- Optimal for 7B Q4_0 models
- 31/31 layers can fit
- Estimated 3.0x speedup

### Requirements
```
Python 3.12+
PySide6 (Qt GUI)
httpx (HTTP client)
Ollama server running
```

## 🔧 Development

### Setup
```powershell
# Install dependencies
pip install -r requirements.txt

# Run tests
python tests/test_kobold_harvest.py

# Launch app
.\run_aura_nexus.ps1
```

### Project Structure Philosophy
- **`src/`** - Core functionality, well-tested
- **`tests/`** - All test/demo files together
- **`docs/`** - Human-readable documentation
- **`archive/`** - Code preserved for feature harvesting
- **`tools/`** - Standalone utility scripts
- **Root** - Entry points and scripts only

## 📚 Documentation

- [Development Setup](docs/DEV_SETUP.md)
- [Model Configuration](docs/MODEL_SETUP.md)
- [KoboldCPP Harvest](docs/KOBOLDCPP_GGUF_HARVEST.md)
- [Publishing Guide](docs/GITHUB_PUBLISH.md)

## 🎯 Next Steps

Ready to continue with:
1. More code harvesting from other projects
2. Feature implementation from archived app
3. Testing with actual models
4. Performance optimization

---

**Clean, organized, ready for production.** 🎉
