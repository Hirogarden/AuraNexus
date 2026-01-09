# 🚀 Tomorrow's Quick Start Checklist

## ✅ Before You Begin
- [ ] Read [TONIGHT_SESSION_SUMMARY.md](./TONIGHT_SESSION_SUMMARY.md)
- [ ] Read [electron-app/QUICKSTART.md](./electron-app/QUICKSTART.md)
- [ ] Coffee/tea ready ☕

## 🔥 Quick Win #1: Fix Multiprocessing (20 min)

### Replace multiprocessing with threading in agent_manager.py

```python
# Change imports at top of file:
# OLD:
from multiprocessing import Process, Queue

# NEW:
from threading import Thread
from queue import Queue

# In start_agent() method, replace:
# OLD:
process = multiprocessing.Process(target=_run_agent, args=(...))

# NEW:
thread = Thread(target=_run_agent, args=(...), daemon=True)
thread.start()
```

**Why this works:** Threads share memory, no pickle serialization needed!

### Test it:
1. Terminal 1: `cd electron-app/backend && python core_app.py`
2. Terminal 2: `cd electron-app && npm start`
3. Type "Hello!" in chat
4. Should see responses from all 4 agents (still mock for now)

## 🔥 Quick Win #2: Add Real LLM (30 min)

### Install Ollama
```powershell
# Download from https://ollama.ai/download
# Or if already installed:
ollama pull phi3
```

### Update base_agent.py generate_response():
```python
import ollama

def generate_response(self, message: str) -> str:
    """Generate response using Ollama"""
    personality = {
        "fighter": "You are a brave fighter, direct and action-oriented.",
        "wizard": "You are a wise wizard, analytical and thoughtful.",
        "cleric": "You are a caring cleric, supportive and nurturing.",
        "dm": "You are a dungeon master, narrative and fair."
    }
    
    response = ollama.chat(
        model='phi3',
        messages=[
            {'role': 'system', 'content': personality[self.config['role']]},
            {'role': 'user', 'content': message}
        ]
    )
    
    emoji = {"fighter": "⚔️", "wizard": "🧙", "cleric": "✨", "dm": "🎲"}
    return f"{emoji[self.config['role']]} {self.config['name']}: {response['message']['content']}"
```

### Test it:
1. Restart backend (Ctrl+C in Terminal 1, then `python core_app.py`)
2. Type "What should we do?" in Electron UI
3. Should see AI-generated responses! 🎉

## 📋 Longer Tasks (If You Have Time)

### Build Production .exe (1-2 hours)
```powershell
# 1. Build Python backend
cd electron-app/backend
pyinstaller --onefile --name AuraNexusBackend core_app.py

# 2. Copy backend .exe to Electron
cp dist/AuraNexusBackend.exe ../resources/

# 3. Update main.js to use bundled backend
# (Change spawn path to resources/AuraNexusBackend.exe)

# 4. Build Electron app
cd ..
npm run build

# Result: dist/AuraNexus-Setup-1.0.0.exe
```

### Add Icon
- [ ] Create or find icon file
- [ ] Save as `assets/icon.ico`
- [ ] Update package.json: `"icon": "assets/icon.ico"`
- [ ] Rebuild

### Memory System
- [ ] Add conversation history to agents
- [ ] Persist to SQLite database
- [ ] Load previous conversations on startup

### Settings UI
- [ ] Create settings page (new HTML file)
- [ ] Model selection dropdown
- [ ] API endpoint configuration
- [ ] Save to config.json

## 🐛 Known Issues to Watch For

### Multiprocessing Still Broken?
**Symptom:** Same pickle error  
**Fix:** Make sure you replaced ALL instances of `Process` with `Thread`  
**Check:** Search for "multiprocessing" in agent_manager.py

### Ollama Not Found?
**Symptom:** Connection refused on port 11434  
**Fix:** Start Ollama: `ollama serve` in new terminal  
**Check:** `curl http://localhost:11434/api/tags`

### Backend Won't Start?
**Symptom:** "Address already in use"  
**Fix:** Kill process on port 8000: `netstat -ano | findstr :8000` → `taskkill /PID <PID> /F`  

### Electron Won't Connect?
**Symptom:** "Backend not ready yet..." forever  
**Fix:** Check Terminal 1 shows "Uvicorn running on http://0.0.0.0:8000"  
**Debug:** Open DevTools (Ctrl+Shift+I) → Console tab for errors

## 💡 Pro Tips

1. **Keep 3 terminals open:**
   - Terminal 1: Backend (python core_app.py)
   - Terminal 2: Electron (npm start)
   - Terminal 3: Ollama (ollama serve) if not running as service

2. **Use split terminals:** Ctrl+Shift+5 in VS Code

3. **Auto-reload backend:** Install `uvicorn[standard]` → use `--reload` flag

4. **Debug Python:** Add `import pdb; pdb.set_trace()` breakpoints

5. **Debug Electron:** Ctrl+Shift+I for DevTools

## 🎯 Success Criteria for Tomorrow

**Minimum:**
- [ ] Agents working with threading (no multiprocessing errors)
- [ ] Real LLM responses from Ollama
- [ ] All 4 agents responding with distinct personalities

**Stretch Goals:**
- [ ] Production .exe built and tested
- [ ] Icon added
- [ ] Memory system started

## 📞 Need Help?

### Quick Debugging Commands
```powershell
# Check if backend running:
curl http://localhost:8000/

# Check Ollama running:
curl http://localhost:11434/api/tags

# Check processes on port 8000:
netstat -ano | findstr :8000

# View backend logs:
# (Just look at Terminal 1)
```

### File Locations
- Backend: `electron-app/backend/core_app.py`
- Agent Manager: `electron-app/backend/agent_manager.py`
- Base Agent: `electron-app/backend/agents/base_agent.py`
- Main Process: `electron-app/main.js`
- UI: `electron-app/index.html`

## 🎉 When It Works...

You'll see:
```
User: "What should we do?"

⚔️ Fighter: "I say we charge in! My sword is ready for whatever comes."
🧙 Wizard: "Let's assess the situation carefully. I can detect magical auras."
✨ Cleric: "May the light guide us. I'll keep everyone healed and safe."
🎲 DM: "The party stands at a crossroads. To the north, dark clouds gather..."
```

## 📚 Reference Documents
- [TONIGHT_SESSION_SUMMARY.md](./TONIGHT_SESSION_SUMMARY.md) - Full session recap
- [electron-app/QUICKSTART.md](./electron-app/QUICKSTART.md) - How to run
- [FauxRAGClaude conversation](../FauxRAGClaude/projects/All-In-One/conversations/2026-01-08_electron-app-session.md) - Detailed context

---

**Good luck tomorrow! You've got a solid foundation to build on. The hardest part (architecture decisions) is done. Now it's just implementation! 🚀**

**Estimated time to working LLM:** ~1 hour  
**Estimated time to production .exe:** ~3 hours  
**Fun factor:** 11/10 when it all comes together! 🎲⚔️🧙✨
