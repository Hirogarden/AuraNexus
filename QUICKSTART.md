# 🚀 Quick Start Guide

## Running AuraNexus

### Option 1: Double-Click (Easiest)
Just double-click **`START_AURANEXUS.bat`** in the root folder.

This will automatically:
1. ✅ Start the frontend dev server (port 1420)
2. ✅ Start the Python backend with AI (port 8000)  
3. ✅ Open the Tauri UI window

**First launch may take 1-2 minutes** while it loads the AI model.

### Option 2: PowerShell
```powershell
.\start-auranexus.ps1
```

### Option 3: Manual (for debugging)
```powershell
# Terminal 1: Frontend dev server
cd tauri-app\ui
node server.js

# Terminal 2: Python backend
.venv\Scripts\Activate.ps1
python -m electron-app.backend.core_app

# Terminal 3: Tauri UI
cd tauri-app
npm run dev
```

## Stopping AuraNexus

Close the Tauri window, then press `Ctrl+C` in the terminal to stop all services.

## Troubleshooting

**"Backend is OFFLINE" in UI:**
- Wait 1-2 minutes for first launch (loading AI model)
- Check if port 8000 is already in use
- Look for errors in the terminal

**"Tauri API Error":**
- Make sure you're using the bat/ps1 launcher
- Try refreshing the window (F5)

**Rust/Cargo errors:**
- Open a new PowerShell and try again (PATH refresh needed)

## What's Running?

- **Port 1420**: Frontend dev server (HTML/CSS/JS)
- **Port 8000**: Python FastAPI backend (AI + memory)
- **Tauri Window**: Desktop app (connects to both)

## Features Available

✅ 13 UI settings (temperature, presets, themes, etc.)
✅ Backend connection status indicator  
✅ Real-time AI responses
✅ 4 async agents (narrator, characters, director)
✅ Memory system with RAG
✅ HIPAA-compliant in-process LLM
