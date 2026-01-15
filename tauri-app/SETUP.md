# AuraNexus Tauri Setup Guide

## 🎯 What is This?

This is the **Tauri version** of AuraNexus - a lightweight, Rust-secured alternative to Electron.

**Benefits over Electron:**
- ✅ **90% smaller** (~3MB vs ~200MB)
- ✅ **Rust security** (memory-safe, fast)
- ✅ **Lower RAM usage** (uses system webview)
- ✅ **Native performance**

---

## 📋 Prerequisites

### 1. Install Rust
```powershell
# Download and run rustup-init.exe from:
# https://rustup.rs/

# Or use winget:
winget install Rustlang.Rustup
```

### 2. Install Visual Studio Build Tools (Windows)
```powershell
# Download from:
# https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Or use winget:
winget install Microsoft.VisualStudio.2022.BuildTools
```

### 3. Install WebView2 (Usually pre-installed on Windows 11)
```powershell
# Check if installed:
Get-AppxPackage -Name "Microsoft.WebView2*"

# If not, download from:
# https://developer.microsoft.com/microsoft-edge/webview2/
```

### 4. Install Node.js (if not already installed)
```powershell
winget install OpenJS.NodeJS
```

---

## 🚀 Setup & Run

### First Time Setup
```powershell
cd tauri-app

# Install Node dependencies
npm install

# This will download Tauri CLI
```

### Run in Development Mode
```powershell
# Make sure Python backend is running first!
cd C:\Users\hirog\All-In-One\AuraNexus\electron-app
python -m uvicorn backend.core_app:app --host 127.0.0.1 --port 8000

# In a new terminal:
cd C:\Users\hirog\All-In-One\AuraNexus\tauri-app
npm run dev
```

The Tauri app will launch and connect to your Python backend!

---

## 🏗️ Build for Production

```powershell
cd tauri-app
npm run build
```

This creates a **tiny installer** in:
```
tauri-app/src-tauri/target/release/bundle/
```

---

## 🎨 What's Included

### Discord-Style UI
- **Dark theme** matching the Python app
- **Left sidebar** with mode selection (Chatbot, Storyteller, Assistant)
- **Right panel** for settings (collapsible)
- **Smooth animations**
- **Status indicator** (online/offline)

### Rust Backend (Tauri)
- **Secure HTTP requests** to Python backend
- **Type-safe** communication (Serde serialization)
- **Async/await** with Tokio
- **CSP protection** (Content Security Policy)
- **HTTP allowlist** (only localhost:8000)

### Features
- ✅ All 3 modes (Chatbot, Storyteller, Assistant)
- ✅ Agent selection (narrator, character_1, character_2, director)
- ✅ Settings panel (temperature, max tokens)
- ✅ Real-time backend status
- ✅ Message history
- ✅ Keyboard shortcuts (Enter to send)
- ✅ XSS protection (HTML escaping)

---

## 🔧 Troubleshooting

### "Backend Offline" Error
1. Make sure Python backend is running on port 8000
2. Check backend: `Test-NetConnection 127.0.0.1 -Port 8000`
3. Start backend: `python -m uvicorn backend.core_app:app --host 127.0.0.1 --port 8000`

### Rust Compilation Errors
- Install Visual Studio Build Tools
- Restart terminal after installing Rust
- Run: `rustup update`

### WebView2 Missing
- Install from: https://developer.microsoft.com/microsoft-edge/webview2/

---

## 📂 Project Structure

```
tauri-app/
├── ui/                      # Frontend (HTML/CSS/JS)
│   ├── index.html           # Main UI (Discord-style)
│   ├── styles.css           # Dark theme styles
│   └── app.js               # Frontend logic
│
├── src-tauri/               # Rust backend
│   ├── src/
│   │   └── main.rs          # Tauri commands & HTTP client
│   ├── Cargo.toml           # Rust dependencies
│   ├── tauri.conf.json      # Tauri configuration
│   └── build.rs             # Build script
│
├── package.json             # Node dependencies
└── SETUP.md                 # This file
```

---

## 🎯 Next Steps

1. **Install Rust** (if not done)
2. **Run `npm install`** in tauri-app/
3. **Start Python backend**
4. **Run `npm run dev`**
5. **Enjoy the lightweight, secure UI!**

---

## 🆚 Comparison: Tauri vs Electron

| Feature | Tauri | Electron |
|---------|-------|----------|
| **Binary Size** | ~3 MB | ~200 MB |
| **RAM Usage** | ~50 MB | ~150 MB |
| **Security** | Rust (memory-safe) | Node.js |
| **Startup Time** | <1 second | 2-3 seconds |
| **Bundle Size** | ~5 MB | ~100 MB |
| **Webview** | System (Edge/Safari) | Chromium (bundled) |

**Winner: Tauri** 🏆 (for desktop apps)

---

## 🤝 Contributing

This UI matches the Python app's design. To add features:

1. **Frontend**: Edit `ui/app.js` and `ui/index.html`
2. **Backend**: Edit `src-tauri/src/main.rs`
3. **Styles**: Edit `ui/styles.css`

---

**Enjoy your lightweight, secure AuraNexus! 🚀**
