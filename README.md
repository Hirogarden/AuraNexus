# AuraNexus

AuraNexus is a unified desktop application for AI interaction with a clean PySide6 interface powered by Ollama.

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
- Ollama installed and running (https://ollama.com)
- Virtual environment (recommended)

### Installation

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
├── launch.py                 # Main entry point
├── run_auranexus.ps1        # Windows launcher script
├── requirements.txt         # Python dependencies
└── src/
    ├── main.py              # Project launcher UI
    ├── ollama_client.py     # Ollama API client
    └── ollama_chat.py       # Chat interface with save/load
```

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
