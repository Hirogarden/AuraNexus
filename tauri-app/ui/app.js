// Import Tauri API (with fallback check)
let invoke = null;

// Global state
let currentMode = 'chatbot';
let isBackendOnline = true;

// Separate message history for each mode (like Discord channels)
let modeMessages = {
    chatbot: [],
    storyteller: [],
    assistant: []
};

// Initialize Tauri API when available
function initTauri() {
    console.log('Checking for Tauri API...');
    
    // Check for __TAURI_INVOKE__ which is the actual invoke function in Tauri 1.x
    if (window.__TAURI_INVOKE__) {
        invoke = window.__TAURI_INVOKE__;
        console.log('✅ Found invoke at window.__TAURI_INVOKE__');
        console.log('✅ Tauri API loaded successfully');
        return true;
    }
    
    // Fallback checks
    if (window.__TAURI__) {
        if (window.__TAURI__.invoke) {
            invoke = window.__TAURI__.invoke;
            console.log('✅ Found invoke at window.__TAURI__.invoke');
            return true;
        } else if (window.__TAURI__.tauri && window.__TAURI__.tauri.invoke) {
            invoke = window.__TAURI__.tauri.invoke;
            console.log('✅ Found invoke at window.__TAURI__.tauri.invoke');
            return true;
        } else if (window.__TAURI__.core && window.__TAURI__.core.invoke) {
            invoke = window.__TAURI__.core.invoke;
            console.log('✅ Found invoke at window.__TAURI__.core.invoke');
            return true;
        }
    }
    
    console.error('❌ Tauri API not available');
    console.log('Available Tauri keys:', Object.keys(window).filter(k => k.includes('TAURI')));
    return false;
}

// Mode configurations (matching Python app)
const MODE_CONFIG = {
    chatbot: {
        title: '💬 AI Chatbot',
        description: 'Have natural conversations with AI',
        info: 'AI Chatbot: Natural conversations with context awareness',
        defaultAgent: 'narrator',
        showAgentSelector: false,
        systemPrompt: 'You are Aura, a friendly and helpful AI companion. Have natural conversations, be empathetic, and provide thoughtful responses. Keep answers conversational and engaging. Do NOT write in narrative or storytelling style. Do NOT describe scenes or actions. Just chat naturally like a helpful friend.',
        conversationType: 'general'
    },
    storyteller: {
        title: '📖 Storyteller',
        description: 'Create immersive stories and adventures',
        info: 'Storyteller: Generate creative narratives and interactive stories',
        defaultAgent: 'narrator',
        showAgentSelector: true,
        systemPrompt: 'You are a creative storyteller. Help create immersive narratives, describe scenes vividly, and guide interactive story experiences.',
        conversationType: 'storytelling'
    },
    assistant: {
        title: '🤝 AI Assistant',
        description: 'Get help with tasks and information',
        info: 'AI Assistant: Helpful task completion with information retention',
        defaultAgent: 'narrator',
        showAgentSelector: false,
        systemPrompt: 'You are Aura, a professional AI assistant. Help with tasks, provide accurate information, and offer practical solutions. Be clear, concise, and helpful.',
        conversationType: 'assistant'
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
        
        // Initialize status indicator as online
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const sendBtn = document.getElementById('sendBtn');
        indicator.className = 'status-indicator online';
        statusText.textContent = 'Ready';
        sendBtn.disabled = false;
        console.log('✅ Native Rust backend ready');
        
        // Load available models
        refreshModels();
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

// Native Rust backend is always available
// No need for health checks - Tauri commands work directly

// Switch modes
function switchMode(mode) {
    console.log(`Switching from ${currentMode} to ${mode}`);
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
    
    // Update system prompt for this mode
    document.getElementById('systemPrompt').value = config.systemPrompt;
    
    // Show/hide agent selector based on mode
    const agentGroup = document.querySelector('.setting-group:has(#agentSelect)');
    if (agentGroup) {
        if (config.showAgentSelector) {
            agentGroup.style.display = 'block';
        } else {
            agentGroup.style.display = 'none';
        }
    }
    
    // Load messages for this mode (like switching Discord channels)
    loadModeMessages();
}

// Load messages for current mode
function loadModeMessages() {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';
    
    // Reload all messages for this mode
    modeMessages[currentMode].forEach(msg => {
        const msgDiv = createMessageElement(msg.text, msg.type, msg.sender);
        msgDiv.id = msg.id;
        container.appendChild(msgDiv);
    });
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
    
    console.log(`Loaded ${modeMessages[currentMode].length} messages for ${currentMode} mode`);
}

// Create message element
function createMessageElement(text, type, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;
    
    if (sender && type !== 'system' && type !== 'error') {
        const senderSpan = document.createElement('div');
        senderSpan.className = 'message-sender';
        senderSpan.textContent = sender;
        
        const textSpan = document.createElement('div');
        textSpan.className = 'message-text';
        textSpan.textContent = text;
        
        msgDiv.appendChild(senderSpan);
        msgDiv.appendChild(textSpan);
    } else {
        const textSpan = document.createElement('div');
        textSpan.className = 'message-text';
        textSpan.textContent = text;
        msgDiv.appendChild(textSpan);
    }
    
    return msgDiv;
}

// Toggle settings panel
function toggleSettings() {
    const panel = document.getElementById('settingsPanel');
    panel.classList.toggle('hidden');
}

// Clear chat
function clearChat() {
    modeMessages[currentMode] = [];
    document.getElementById('messagesContainer').innerHTML = '';
    console.log(`Cleared chat for ${currentMode} mode`);
}

// Send message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    if (!invoke) {
        console.error('❌ Invoke function not available');
        return;
    }
    
    // Clear input
    input.value = '';
    
    // Add user message
    addMessage(message, 'user', 'You');
    
    // Show loading
    const loadingId = addMessage('Thinking...', 'agent loading', 'AI');
    
    try {
        // Get agent - use mode's default agent if selector is hidden
        const config = MODE_CONFIG[currentMode];
        const agent = config.showAgentSelector 
            ? document.getElementById('agentSelect').value 
            : config.defaultAgent;
        
        console.log(`Sending message in ${currentMode} mode with agent: ${agent}`);
        
        // Get system prompt from textarea
        const systemPrompt = document.getElementById('systemPrompt').value.trim();
        
        // Call Tauri backend (Rust) which calls Python backend
        const response = await invoke('send_chat_message', {
            message: message,
            agent: agent,
            conversation_type: config.conversationType,
            system_prompt: systemPrompt || config.systemPrompt
        });
        
        // Remove loading message
        removeMessage(loadingId);
        
        // Add AI response (show as "AI" for single-agent modes)
        const displayName = config.showAgentSelector ? response.agent : 'AI';
        addMessage(response.response, 'agent', displayName);
        
    } catch (error) {
        console.error('Send message failed:', error);
        removeMessage(loadingId);
        addMessage('❌ ' + error, 'error', 'System');
    }
}

// Add message to UI
function addMessage(text, type, sender) {
    const container = document.getElementById('messagesContainer');
    const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    const messageDiv = createMessageElement(text, type, sender);
    messageDiv.id = messageId;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
    
    // Store in mode-specific message array
    modeMessages[currentMode].push({ id: messageId, text, type, sender });
    
    return messageId;
}

// Remove message by ID
function removeMessage(messageId) {
    const element = document.getElementById(messageId);
    if (element) {
        element.remove();
    }
    // Remove from mode-specific array
    modeMessages[currentMode] = modeMessages[currentMode].filter(m => m.id !== messageId);
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

// Model Management
async function refreshModels() {
    console.log('🔄 Refreshing models...');
    const select = document.getElementById('modelSelect');
    
    if (!invoke) {
        console.error('❌ Tauri invoke not available');
        select.innerHTML = '<option value="">Error: API not available</option>';
        return;
    }
    
    select.innerHTML = '<option value="">🔍 Scanning...</option>';
    
    try {
        const models = await invoke('get_available_models');
        console.log('✅ Found models:', models);
        
        if (models.length === 0) {
            select.innerHTML = '<option value="">No models found</option>';
        } else {
            select.innerHTML = models.map(model => 
                `<option value="${model.path}" title="${model.path}">${model.name} (${model.size_human})</option>`
            ).join('');
        }
    } catch (error) {
        console.error('❌ Failed to load models:', error);
        select.innerHTML = '<option value="">Error loading models</option>';
    }
}

function onModelChange() {
    const select = document.getElementById('modelSelect');
    const modelPath = select.value;
    console.log('📦 Selected model:', modelPath);
    // TODO: Implement model switching (requires backend changes)
}
