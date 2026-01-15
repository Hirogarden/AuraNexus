// Import Tauri API (with fallback check)
let invoke = null;

// Global state
let currentMode = 'chatbot';
let messages = [];
let isBackendOnline = false;

// Initialize Tauri API when available
function initTauri() {
    if (window.__TAURI__ && window.__TAURI__.tauri) {
        invoke = window.__TAURI__.tauri.invoke;
        console.log('✅ Tauri API loaded successfully');
        return true;
    } else {
        console.error('❌ Tauri API not available');
        return false;
    }
}

// Mode configurations (matching Python app)
const MODE_CONFIG = {
    chatbot: {
        title: '💬 AI Chatbot',
        description: 'Have natural conversations with AI',
        info: 'AI Chatbot: Natural conversations with context awareness'
    },
    storyteller: {
        title: '📖 Storyteller',
        description: 'Create immersive stories and adventures',
        info: 'Storyteller: Generate creative narratives and interactive stories'
    },
    assistant: {
        title: '🤝 AI Assistant',
        description: 'Get help with tasks and information',
        info: 'AI Assistant: Helpful task completion with information retention'
    }
};

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing...');
    
    // Wait a bit for Tauri to be ready
    setTimeout(() => {
        if (!initTauri()) {
            document.getElementById('statusText').textContent = 'Tauri API Error';
            return;
        }
        
        checkBackendStatus();
        
        // Check backend every 5 seconds
        setInterval(checkBackendStatus, 5000);
    }, 100);
    
    // Temperature slider
    document.getElementById('temperature').addEventListener('input', (e) => {
        document.getElementById('tempValue').textContent = e.target.value;
    });
    
    // Target sentences auto-calculator
    document.getElementById('targetSentences').addEventListener('input', (e) => {
        const sentences = parseInt(e.target.value) || 3;
    if (!invoke) {
        console.error('❌ Invoke function not available');
        return;
    }
    
        const estimatedTokens = Math.min(4096, Math.max(50, sentences * 35));
        document.getElementById('maxTokens').value = estimatedTokens;
    });
    
    // Apply balanced preset by default
    applySamplingPreset();
});

// Check if backend is online
async function checkBackendStatus() {
    try {
        console.log('Checking backend status...');
        const online = await invoke('check_backend');
        console.log('Backend status result:', online);
        isBackendOnline = online;
        
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const sendBtn = document.getElementById('sendBtn');
        
        if (online) {
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Backend Online';
            sendBtn.disabled = false;
            console.log('✅ Backend is ONLINE');
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = 'Backend Offline';
            sendBtn.disabled = true;
            console.log('❌ Backend is OFFLINE');
        }
    } catch (error) {
        console.error('❌ Status check FAILED:', error);
        isBackendOnline = false;
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const sendBtn = document.getElementById('sendBtn');
        indicator.className = 'status-indicator offline';
        statusText.textContent = 'Connection Error';
        sendBtn.disabled = true;
    }
}

// Switch modes
function switchMode(mode) {
    currentMode = mode;
    
    // Update active button
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-mode="${mode}"]`).classList.add('active');
    
    // Update header
    const config = MODE_CONFIG[mode];
    document.getElementById('modeTitle').textContent = config.title;
    document.getElementById('modeDescription').textContent = config.description;
    document.getElementById('currentModeInfo').textContent = config.info;
    
    // Clear messages for new mode (optional)
    // clearChat();
}

// Toggle settings panel
function toggleSettings() {
    const panel = document.getElementById('settingsPanel');
    panel.classList.toggle('hidden');
}

// Clear chat
function clearChat() {
    messages = [];
    if (!invoke) {
        console.error('❌ Invoke function not available');
        return;
    }
    
    document.getElementById('messagesContainer').innerHTML = '';
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !isBackendOnline) return;
    
    // Clear input
    input.value = '';
    
    // Add user message
    addMessage(message, 'user', 'You');
    
    // Show loading
    const loadingId = addMessage('Thinking...', 'agent loading', 'AI');
    
    try {
        // Get selected agent
        const agent = document.getElementById('agentSelect').value;
        
        // Call Tauri backend (Rust) which calls Python backend
        const response = await invoke('send_chat_message', {
            message: message,
            agent: agent
        });
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Add AI response
        addMessage(response.response, 'agent', response.agent);
        
    } catch (error) {
        console.error('Send message failed:', error);
        removeMessage(loadingId);
        addMessage('❌ ' + error, 'error', 'System');
    }
}

// Add message to UI
function addMessage(text, type, sender) {
    const container = document.getElementById('messagesContainer');
    const messageDiv = document.createElement('div');
    const messageId = 'msg_' + Date.now();
    
    messageDiv.id = messageId;
    messageDiv.className = `message ${type}`;
    
    if (sender && type !== 'system' && type !== 'error') {
        messageDiv.innerHTML = `
            <div class="message-sender">${sender}</div>
            <div class="message-text">${escapeHtml(text)}</div>
        `;
    } else {
        messageDiv.innerHTML = `<div class="message-text">${escapeHtml(text)}</div>`;
    }
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
    
    messages.push({ id: messageId, text, type, sender });
    
    return messageId;
}

// Remove message by ID
function removeMessage(messageId) {
    const element = document.getElementById(messageId);
    if (element) {
        element.remove();
    }
    messages = messages.filter(m => m.id !== messageId);
}

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Apply sampling preset
function applySamplingPreset() {
    const preset = document.getElementById('samplingPreset').value;
    
    // Sampling presets from old AuraNexus and backend llm_manager.py
    const presets = {
        balanced: {
            temperature: 0.7,
            top_p: 0.9,
            top_k: 40,
            repeat_penalty: 1.05,
            max_tokens: 512
        },
        creative: {
            temperature: 1.0,
            top_p: 0.95,
            top_k: 50,
            repeat_penalty: 1.1,
            max_tokens: 512
        },
        assistant: {
            temperature: 0.3,
            top_p: 0.9,
            top_k: 40,
            repeat_penalty: 1.1,
            max_tokens: 350
        },
        factual: {
            temperature: 0.2,
            top_p: 0.85,
            top_k: 30,
            repeat_penalty: 1.15,
            max_tokens: 400
        }
    };
    
    if (preset !== 'custom' && presets[preset]) {
        const config = presets[preset];
        document.getElementById('temperature').value = config.temperature;
        document.getElementById('tempValue').textContent = config.temperature;
        document.getElementById('topP').value = config.top_p;
        document.getElementById('topPValue').textContent = config.top_p;
        document.getElementById('topK').value = config.top_k;
        document.getElementById('repeatPenalty').value = config.repeat_penalty;
        document.getElementById('repeatValue').textContent = config.repeat_penalty;
        document.getElementById('maxTokens').value = config.max_tokens;
    }
}

// Apply theme
function applyTheme() {
    const theme = document.getElementById('themeSelect').value;
    const root = document.documentElement;
    
    const themes = {
        dark: {
            '--bg-primary': '#2B2D31',
            '--bg-secondary': '#1E1F22',
            '--bg-tertiary': '#383A40',
            '--text-primary': '#DBDEE1',
            '--text-secondary': '#B5BAC1',
            '--accent': '#5865F2',
            '--accent-hover': '#4752C4'
        },
        midnight: {
            '--bg-primary': '#0d1117',
            '--bg-secondary': '#010409',
            '--bg-tertiary': '#161b22',
            '--text-primary': '#c9d1d9',
            '--text-secondary': '#8b949e',
            '--accent': '#58a6ff',
            '--accent-hover': '#4184e4'
        },
        solarized: {
            '--bg-primary': '#002b36',
            '--bg-secondary': '#073642',
            '--bg-tertiary': '#586e75',
            '--text-primary': '#839496',
            '--text-secondary': '#657b83',
            '--accent': '#268bd2',
            '--accent-hover': '#2aa198'
        },
        light: {
            '--bg-primary': '#ffffff',
            '--bg-secondary': '#f6f6f6',
            '--bg-tertiary': '#e3e5e8',
            '--text-primary': '#060607',
            '--text-secondary': '#4e5058',
            '--accent': '#5865F2',
            '--accent-hover': '#4752C4'
        }
    };
    
    if (themes[theme]) {
        Object.entries(themes[theme]).forEach(([key, value]) => {
            root.style.setProperty(key, value);
        });
    }
}

// Apply UI scale
function applyUIScale(size) {
    document.body.style.fontSize = size + 'px';
}
