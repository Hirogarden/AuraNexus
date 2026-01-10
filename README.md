# AuraNexus

AuraNexus is a **HIPAA-compliant mental health support platform** with AI interaction capabilities. Built as a secure, local-first desktop application with end-to-end encryption and in-process AI inference.

> **⚠️ Security First:** This application is designed to handle Protected Health Information (PHI) for mental health support. All data stays on your device, encrypted at rest, with no external network calls for sensitive data. See [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) for full details.

## 📚 For Developers: HIPAA Compliance Documentation

**NEW TO THE PROJECT? START HERE:**
1. 📖 [COMPLIANCE_DOCS_INDEX.md](./COMPLIANCE_DOCS_INDEX.md) - Master guide to all documentation
2. ⚖️ [HIPAA_COMPLIANCE.md](./HIPAA_COMPLIANCE.md) - Core security framework (MUST READ before coding)
3. ✅ [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) - Complete for EVERY feature (no exceptions)
4. 📋 [HIPAA_QUICK_REFERENCE.md](./HIPAA_QUICK_REFERENCE.md) - Daily reference (keep open while coding)
5. 🔄 [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md) - Step-by-step secure development process

**LATEST SESSION:** [SESSION_SUMMARY_2026-01-10.md](./SESSION_SUMMARY_2026-01-10.md) - Complete summary of Phase 1 & 2 design

## 🔒 Security Features

- **In-Process LLM:** All AI inference runs locally within the application (no external API calls)
- **Encrypted Storage:** AES-256-GCM encryption for all conversations, memories, and user data (Phase 2)
- **Zero Network PHI:** Protected Health Information never leaves your device
- **Audit Logging:** Complete audit trail of all data access (Phase 2)
- **Local-First:** Works completely offline, no cloud dependencies
- **Mental Health Focus:** Purpose-built for therapeutic conversation and emotional support

## 🚀 Quick Start

**Windows (Recommended):**
```powershell
.\run_aura_nexus.ps1
```

**Manual Launch:**
```bash
python chat_launcher.py
```

**Direct Python:**
```bash
python -c "import sys; sys.path.insert(0, 'src'); from ollama_chat import OllamaChatWindow; from PySide6.QtWidgets import QApplication; app = QApplication([]); win = OllamaChatWindow(project_name='Chat'); win.show(); app.exec()"
```

## Features

- **AI Chat Interface:**
  - Multiple Ollama model support with dynamic switching
  - Real-time health monitoring (shows Ollama version & status)
  - Structured outputs, tool calling, embeddings support
  - Local GGUF model support (llama-cpp-python)

- **Memory System (RAG):**
  - **Built-in RAG:** Lightweight Python-based memory using ChromaDB
  - **AnythingLLM Support:** Optional integration with external AnythingLLM instance
  - **Save to Memory:** Store conversations for future context retrieval
  - **Automatic Context:** Relevant past conversations enhance responses

- **Core Capabilities:**
  - Conversation save/load to JSON files
  - Clean, responsive chat interface
  - Comprehensive error handling with AsyncOllamaClient
  - Real-time status updates with version display

## Prerequisites

- Python 3.12+
- 8GB+ RAM (16GB recommended for larger models)
- Virtual environment (recommended)
- **No external services required** (fully self-contained)

### Optional Components
- Ollama (for legacy mode, not required for HIPAA-compliant mode)
- GPU with 8GB+ VRAM (for faster inference, CPU works fine)

## Installation

```powershell
# Windows PowerShell
cd AuraNexus
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
cd AuraNexus
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running AuraNexus

**Windows:**
```powershell
.\run_auranexus.ps1
```
or
```powershell
.\.venv\Scripts\python.exe launch.py
```

**macOS / Linux:**
```bash
python launch.py
```

## Project Structure

```
AuraNexus/
├── HIPAA_COMPLIANCE.md           # ⚠️ SECURITY FRAMEWORK (READ FIRST)
├── SECURITY_CHECKLIST.md         # Feature development checklist
├── launch.py                     # Main entry point (legacy)
├── run_auranexus.ps1            # Windows launcher script
├── requirements.txt              # Python dependencies
├── electron-app/                 # New Electron + FastAPI app
│   ├── backend/
│   │   ├── core_app.py          # FastAPI server
│   │   ├── llm_manager.py       # In-process LLM (HIPAA-compliant)
│   │   ├── agent_manager_async.py  # Async agent orchestration
│   │   └── agents/
│   │       └── async_agent.py   # Individual AI agents
│   ├── test_inprocess_llm.py    # LLM testing
│   ├── INPROCESS_LLM_ARCHITECTURE.md  # Architecture docs
│   └── models/                   # Local GGUF models go here
└── src/                          # Legacy PySide6 interface
    ├── main.py                   # Project launcher UI
    ├── ollama_client.py          # Ollama API client (legacy)
    └── ollama_chat.py            # Chat interface (legacy)
### New (HIPAA-Compliant) Backend

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Start FastAPI backend
cd electron-app
uvicorn backend.core_app:app --reload --port 8001

# Test in-process LLM
python test_inprocess_llm.py
```

**Endpoints:**
- `POST /chat` - Send message to specific agent
- `POST /broadcast` - Broadcast to all agents
**Core (HIPAA-Compliant):**
- FastAPI (async web framework)
- llama-cpp-python (in-process LLM inference)
- asyncio (async agent architecture)
- SQLCipher (encrypted database, Phase 2)
- Mem0 + ChromaDB (local memory, Phase 2)

**Legacy (Non-Compliant):**
- PySide6 (GUI framework)
- requests (HTTP client)
- Ollama (extern
### Legacy Interface

1. Ensure Ollama is running (`ollama serve`)
2. Launch AuraNexus with `python launch.py`
3. Select a project mode
4. Choose your model
5. Start chatting

**⚠️ Note:** Legacy mode is not HIPAA-compliant (uses external Ollama server).tAPI with async agents
- **LLM:** llama-cpp-python (in-process, no external calls)
- **Storage:** SQLite with encryption (Phase 2)
- **Memory:** Mem0 + ChromaDB (local vector DB, Phase 2)
- **Frontend:** Electron (in development)

**Legacy (Non-Compliant):**
- PySide6 interface with Ollama external server
- See migration guide for transitioning to compliant architecture

## Requirements

- PySide6 (GUI framework)
- requests (HTTP client)
- chromadb (built-in RAG memory)
- sentence-transformers (text embeddings)
- Ollama (local LLM server)

## Usage

1. Ensure Ollama is running (`ollama serve`)
2. Launch AuraNexus
3. Select a project mode (A, B, or C)
4. Choose your preferred model from the dropdown
5. (Optional) Enable memory system for context retention
6. Start chatting!

### Memory System

**Built-in RAG (Default):**
- Works out of the box, no configuration needed
- Stores memories locally in `data/rag/` directory
- Click "Save to Memory" to store conversations
- Automatically retrieves relevant context for future chats

**AnythingLLM (Optional):**
- If you have AnythingLLM running, it will be auto-detected
- Select "AnythingLLM" from the Memory dropdown
- Provides advanced RAG features and document management

### Saving Conversations

**Save Conversation:** Export chat to JSON file for archival
**Save to Memory:** Add conversation to RAG for future context (requires memory system enabled)

## Development Notes

This application integrates with Ollama for local LLM inference, providing a flexible and privacy-focused AI assistant experience without requiring cloud services.
