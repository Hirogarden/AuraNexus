# AuraNexus

**Your Personal AI Companion - Private, Offline, Versatile**

AuraNexus is a fully offline AI assistant that runs locally on your computer. No cloud, no tracking, no data collection - just you and your AI companion working together on whatever you need.

## 🌟 What Makes AuraNexus Different

- **100% Offline:** Everything runs on your device. No internet required after setup.
- **Private by Default:** Your conversations never leave your computer. No logs, no tracking, no cloud storage.
- **Versatile Modes:** Switch between helpful assistant mode and creative storytelling mode
- **Modern UI:** Beautiful dark-themed interface built with Tauri and React
- **Military-Grade Encryption:** Optional AES-256-GCM encryption for stored conversations
- **Open Source:** Built with transparency and user control in mind

## 🎭 Modes

### 💜 Companion Mode
Your everyday AI assistant for:
- Answering questions and providing information
- Brainstorming ideas and solving problems  
- Having engaging conversations
- Helping with tasks and projects
- Whatever you need in the moment

### 🧡 AI 'You'niverse
Your creative storytelling partner for:
- Interactive fiction and narrative adventures
- Character development and world-building
- Exploring different genres and settings
- Collaborative story creation
- Bringing your imagination to life

## 🚀 Quick Start

**Requirements:**
- Windows 10/11
- Python 3.10 or higher
- 8GB RAM minimum (16GB recommended for larger models)

**Installation:**
```powershell
# Clone the repository
git clone https://github.com/yourusername/AuraNexus.git
cd AuraNexus

# Set up Python environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Launch the app
cd tauri-app
npm install
npm run dev  # In one terminal
npx tauri dev  # In another terminal
```

## 🎨 Features

- **Clean, Modern Interface:** Dark-themed UI with smooth animations
- **Local LLM Support:** Use any GGUF format language model
- **Conversation Memory:** Persistent chat history across sessions
- **Mode Switching:** Seamlessly switch between assistant and storytelling modes
- **Quality Indicators:** See confidence scores on AI responses
- **Search:** Find past conversations and memories
- **Fully Offline:** No internet connection needed after initial setup

## 🛡️ Privacy & Security

AuraNexus takes your privacy seriously:

- **No Telemetry:** We don't collect any data, ever
- **No Cloud Sync:** Everything stays on your device
- **No External APIs:** All AI processing happens locally
- **Optional Encryption:** Secure your conversation history with AES-256
- **No Account Required:** No sign-up, no login, no tracking

Your data is yours, period.

## 🏗️ Architecture

**Frontend:** React 18 + Vite 5 + Tauri 1.5
**Backend:** Rust (Tauri) + Python (llama-cpp-python)
**Storage:** Local SQLite database
**AI:** In-process inference with llama.cpp

## 📖 Documentation

- [Getting Started Guide](./docs/GETTING_STARTED.md)
- [Model Selection Guide](./docs/MODELS.md)
- [Configuration Options](./docs/CONFIGURATION.md)
- [Privacy & Security](./docs/PRIVACY.md)
- [Contributing Guide](./CONTRIBUTING.md)

## 🤝 Contributing

We welcome contributions! Whether it's:
- Bug reports and feature requests
- Documentation improvements
- Code contributions
- UI/UX suggestions

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## 📜 License

AuraNexus is open source software licensed under the Apache License 2.0.

See [LICENSE](./LICENSE) for full details.

## 🙏 Acknowledgments

Built with:
- [Tauri](https://tauri.app/) - Lightweight desktop framework
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Local LLM inference
- [React](https://react.dev/) - UI framework
- [Vite](https://vitejs.dev/) - Build tooling

## 💬 Community & Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/AuraNexus/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/AuraNexus/discussions)

---

**AuraNexus** - Your personal AI companion. Private, offline, and built for you.
