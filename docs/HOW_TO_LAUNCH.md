# How to Launch AuraNexus

## ✅ CORRECT Ways to Launch

### Option 1: PowerShell Script (Recommended)
```powershell
.\run_aura_nexus.ps1
```
- Automatically handles virtual environment
- Installs missing dependencies
- Launches `aura_nexus_app.py`

### Option 2: Direct Python
```bash
python aura_nexus_app.py
```
- Make sure you're in the virtual environment first:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```

### Option 3: Launch Script
```bash
python launch.py
```
- Simpler alternative, just runs `aura_nexus_app.py`

---

## ❌ OLD/DEPRECATED Launchers

### `src/main.py` - DEPRECATED
- **DO NOT USE** - This is from the old program
- Will show error message and exit
- Kept for reference only (code will be harvested later)
- Shows: `DEPRECATED: This launcher is from the old program`

### `ai_launcher.py` - DEPRECATED
- **DO NOT USE** - Already marked deprecated
- Shows: `[Deprecated] GUI launcher removed. Run: run_aura_nexus.ps1`

---

## 📂 Current Application Structure

```
AuraNexus/
├── aura_nexus_app.py          ← MAIN APPLICATION (use this)
├── run_aura_nexus.ps1         ← LAUNCHER SCRIPT (use this)
├── launch.py                  ← Simple launcher wrapper
├── src/
│   ├── ollama_client.py       ← Upgraded AsyncOllamaClient
│   ├── ollama_chat.py         ← Chat window component
│   ├── main.py                ← OLD/DEPRECATED (don't use)
│   └── ...
├── app/
│   └── aura_launcher.py       ← Service manager (for dev)
└── ...
```

---

## 🎯 What Each File Does

| File | Status | Purpose |
|------|--------|---------|
| `aura_nexus_app.py` | ✅ **CURRENT** | Main GUI application with upgraded AsyncOllamaClient |
| `run_aura_nexus.ps1` | ✅ **CURRENT** | Recommended launcher script |
| `launch.py` | ✅ **CURRENT** | Simple Python launcher |
| `src/main.py` | ❌ **DEPRECATED** | Old project launcher from previous program |
| `ai_launcher.py` | ❌ **DEPRECATED** | Old GUI launcher (removed) |
| `app/aura_launcher.py` | 🔧 **DEV TOOL** | Service manager (start/stop services) |

---

## 🔍 How to Tell Which App is Running

### Current App (aura_nexus_app.py):
- Window title: **"Aura Nexus"**
- Health status shows: **"Ready (v0.13.5)"** with Ollama version
- Tooltip shows: **"Ollama 0.13.5 | Current: model | Available: model1, model2"**
- Has tabs: Chat, Settings, Services, Models, Avatar
- Shows real-time health monitoring

### Old App (src/main.py):
- Window title: **"AuraNexus - Project Launcher"** 
- Shows project selection buttons (Project A, B, C)
- Different UI layout
- **Should never open** - now shows deprecation error

---

## 🐛 Troubleshooting

### "Old launcher opened instead"
1. Make sure you're running `python aura_nexus_app.py` NOT `python src/main.py`
2. The correct launcher has integrated Ollama health checks
3. Old launcher will show deprecation message and exit

### "Health check shows offline"
1. Start Ollama: `ollama serve` or `ollama list`
2. Check if port 11434 is accessible
3. Wait a few seconds for Ollama to initialize

### "Import errors"
1. Activate virtual environment: `.\.venv\Scripts\Activate.ps1`
2. Install dependencies: `pip install -r requirements.txt`
3. Make sure `src/ollama_client.py` exists

---

## ✨ Recent Upgrades

The current app (`aura_nexus_app.py`) now includes:
- ✅ AsyncOllamaClient with httpx
- ✅ Non-blocking health checks
- ✅ Version display in UI
- ✅ Better error handling
- ✅ Context managers
- ✅ All 14 Ollama API endpoints

See [LAUNCHER_INTEGRATION.md](LAUNCHER_INTEGRATION.md) for details.
