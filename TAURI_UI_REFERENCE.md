# Tauri + React UI Reference

**Complete UI implementation for quick rebuild if needed**

## File Structure
```
tauri-app/
├── ui/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Sidebar.css
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── ChatWindow.css
│   │   │   ├── StatusBar.jsx
│   │   │   └── StatusBar.css
│   │   ├── global.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── src-tauri/
    ├── src/
    │   ├── main.rs
    │   ├── python_bridge.rs
    │   └── lib.rs
    ├── tauri.conf.json
    └── Cargo.toml
```

## Design System

### Color Palette
- Background: `#0a0a0a` (deep space black)
- Sidebar: `#1a1a1a`
- Surface: `#2a2a2a`
- Text Primary: `#e0e0e0`
- Text Secondary: `#a0a0a0`
- Accent Purple: `#8b5cf6` (Companion Mode)
- Accent Orange: `#f59e0b` (You'niverse Mode)
- Border: `#3a3a3a`
- Input Background: `#2a2a2a`
- Button Hover: `rgba(139, 92, 246, 0.1)`

### Typography
- Font: System UI (-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto)
- Logo "Aura": Purple gradient, 24px, bold
- Logo "Nexus": White, 24px, 300 weight
- Mode titles: 16px
- Body text: 14px

### Spacing
- Sidebar width: 280px
- Chat window padding: 24px
- Message gap: 16px
- Input padding: 16px

## Two Modes

### 1. Companion Mode (💜)
- Icon: Heart
- Color: Purple `#8b5cf6`
- System Prompt: "You are a helpful and versatile AI assistant..."

### 2. You'niverse Mode (🧡)
- Icon: BookOpen
- Color: Orange `#f59e0b`
- System Prompt: "You are an imaginative AI storyteller..."

## Component Details

### App.jsx
```jsx
- State: currentMode, messages, isLoading, currentModel
- Modes: companion, youniverse
- Tauri invoke: send_chat_message, check_backend, get_current_mode
- Message handling: User input → Loading state → Stream response
```

### Sidebar.jsx
```jsx
- Logo with gradient (Aura = purple, Nexus = white)
- Two mode buttons with icons, titles, descriptions
- Active state: border-left 3px + background highlight
- Settings button (⚙️) at bottom
- Clear Chat button (🗑️) in red
- Status indicator at bottom
```

### ChatWindow.jsx
```jsx
- Messages mapped from state
- User messages: right-aligned, purple bubble
- AI messages: left-aligned, dark bubble
- Input box: multiline, auto-expand
- Send button: purple, right side
- Loading animation: "Thinking..." with fade
- Auto-scroll to bottom on new messages
```

### StatusBar.jsx
```jsx
- Model name display (left)
- Backend status: Ready/Error (center)
- Token count (right, optional)
- 40px height, dark background
```

## Rust Backend Integration

### main.rs - 7 Tauri Commands
1. `send_chat_message(message, mode)` → `Result<String>`
2. `check_backend()` → `Result<String>`
3. `switch_mode(mode)` → `Result<()>`
4. `search_conversations(query)` → `Result<Vec<SearchResult>>`
5. `get_conversation_history(limit)` → `Result<Vec<ConversationEntry>>`
6. `get_current_mode()` → `Result<String>`
7. `initialize_model(model_name)` → `Result<()>`

### python_bridge.rs - PyO3 Integration
```rust
- PythonBridge struct with backend_path
- find_backend_path() - searches electron-app.OLD/backend
- initialize() - imports llm_manager.py, hierarchical_memory.py
- generate_response() - calls Python generate_with_context()
- get_available_models() - calls Python find_available_model()
- sys.path includes both backend/ and workspace root
```

### Python Helper Functions (in llm_manager.py)
```python
def find_available_model():
    """Search for .gguf models in workspace"""

def generate_with_context(
    prompt: str,
    mode: str = "companion",
    max_tokens: int = 512,
    temperature: float = 0.7
) -> str:
    """Generate response with hierarchical memory context"""
```

## Package.json Scripts
```json
"dev": "vite",
"build": "vite build",
"preview": "vite preview"
```

## Vite Config
```js
export default {
  server: { port: 1420 },
  clearScreen: false,
  envPrefix: ['VITE_', 'TAURI_']
}
```

## Tauri Config
```json
{
  "build": {
    "beforeDevCommand": "",  // Empty - manual Vite start
    "devPath": "http://localhost:1420",
    "distDir": "../ui/dist"
  },
  "package": {
    "productName": "AuraNexus",
    "version": "2.0.0"
  },
  "tauri": {
    "windows": [
      {
        "title": "AuraNexus",
        "width": 1400,
        "height": 900,
        "minWidth": 800,
        "minHeight": 600
      }
    ]
  }
}
```

## Launch Process
1. Terminal 1: `cd tauri-app/ui && npm run dev` (Vite on :1420)
2. Terminal 2: `cd tauri-app && npx tauri dev` (Rust + Tauri)
3. Window opens with gradient logo
4. Python backend initializes (debug logs with 🔍🐍✅❌)
5. Select mode → Chat → Send message → AI response

## Key Features
- Real-time mode switching
- Message history persistence
- Hierarchical memory integration
- Quality indicator display
- Model dropdown selection
- Dark theme throughout
- Responsive layout
- Smooth animations

## Dependencies
### UI (package.json)
- react: 18.2
- react-dom: 18.2
- @tauri-apps/api: 1.5
- vite: 5.0

### Rust (Cargo.toml)
- tauri: 1.5
- pyo3: 0.20
- serde: 1.0
- serde_json: 1.0
- anyhow: 1.0

## Notes
- Backend path: `electron-app.OLD/backend/` (Python)
- Nexus Core modules: workspace root (nexus_core_*.py)
- Optional encryption: AES-256-GCM
- Fully offline, no external API calls
