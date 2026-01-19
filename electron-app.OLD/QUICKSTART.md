# AuraNexus Electron App - Quick Start Guide

## 🚀 How to Run (Development)

### Prerequisites
- Node.js installed
- Python 3.12+ with virtual environment configured
- Dependencies installed (see below)

### Installation

1. **Install Node Dependencies:**
```powershell
cd electron-app
npm install
```

2. **Install Python Dependencies:**
```powershell
cd backend
pip install -r requirements.txt
```

### Running the App

**You need TWO separate terminals running simultaneously:**

#### Terminal 1: Python Backend
```powershell
cd c:\Users\hirog\All-In-One\AuraNexus\electron-app\backend
python core_app.py
```

You should see:
```
INFO:__main__:Backend ready (agents disabled temporarily)
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal running!**

#### Terminal 2: Electron App
```powershell
cd c:\Users\hirog\All-In-One\AuraNexus\electron-app
npm start
```

Electron window will open with the chat interface.

### Using the App

1. Type a message in the chat input
2. Click "Send" or press Enter
3. You'll see responses from the DND party:
   - ⚔️ Fighter: Direct and action-oriented
   - 🧙 Wizard: Wise and analytical
   - ✨ Cleric: Caring and supportive
   - 🎲 DM: Narrative and storytelling

## 📁 Project Structure

```
electron-app/
├── main.js              # Electron main process
├── preload.js           # Secure IPC bridge
├── index.html           # Chat UI (beautiful gradient design)
├── package.json         # Node dependencies
├── backend/
│   ├── core_app.py      # FastAPI server
│   ├── agent_manager.py # Multi-agent orchestration (disabled on Windows)
│   ├── agents/
│   │   └── base_agent.py # Agent base class
│   └── requirements.txt # Python dependencies
└── README.md
```

## 🔧 Current Status

### ✅ Working
- Electron app launches successfully
- Beautiful gradient chat interface
- FastAPI backend on port 8000
- Mock DND party responses
- Graceful error handling

### ⚠️ Known Issues
- **Windows multiprocessing:** Agent processes disabled due to `pickle` errors with Queue objects
- Using mock responses instead of real agent processes
- No icon file yet (assets/icon.ico missing)

### 🚧 Next Steps
1. Fix multiprocessing (use threading or HTTP-based agents)
2. Integrate Ollama/KoboldCPP for real LLM responses
3. Add character personalities with system prompts
4. Build production .exe with electron-builder
5. Bundle Python backend with PyInstaller
6. Create single-file installer

## 🛠️ Troubleshooting

### Backend won't start
- Check Python is in PATH: `python --version`
- Verify virtual environment is activated
- Install dependencies: `pip install -r requirements.txt`

### Electron can't connect to backend
- Make sure backend terminal shows "Uvicorn running on http://0.0.0.0:8000"
- Backend must stay running in separate terminal
- Don't close backend terminal!

### "Backend not ready yet..." message
- Backend isn't running or failed to start
- Check Terminal 1 for errors
- Restart backend: `python core_app.py`

## 📦 Building Production .exe

```powershell
# Build backend into standalone Python bundle
cd backend
pyinstaller --onefile core_app.py

# Build Electron app with bundled backend
cd ..
npm run build
```

This creates a single 200MB .exe in `dist/` folder.

## 💡 Tips

- Use VS Code's split terminal (Ctrl+Shift+5) for side-by-side terminals
- Or use Windows Terminal with multiple panes
- Backend logs appear in Terminal 1
- Electron logs appear in Terminal 2 and DevTools (Ctrl+Shift+I)

## 🎯 Architecture Vision

**Desktop App (Electron + Python):**
- No Docker required for end users
- Double-click simplicity
- Discord-like experience
- Pre-bundled models (Phi-3-mini for multilingual)
- Automatic updates via GitHub releases

**Target Users:**
- 32GB+ RAM systems
- Want offline AI chat
- Don't want to deal with Docker
- Prefer "just works" experience
