// Import Tauri API
const { invoke } = window.__TAURI__.tauri;

// Global state
let currentMode = 'chatbot';
let messages = [];
let isBackendOnline = false;

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
    checkBackendStatus();
    
    // Check backend every 5 seconds
    setInterval(checkBackendStatus, 5000);
    
    // Temperature slider
    document.getElementById('temperature').addEventListener('input', (e) => {
        document.getElementById('tempValue').textContent = e.target.value;
    });
});

// Check if backend is online
async function checkBackendStatus() {
    try {
        const online = await invoke('check_backend');
        isBackendOnline = online;
        
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const sendBtn = document.getElementById('sendBtn');
        
        if (online) {
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Backend Online';
            sendBtn.disabled = false;
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = 'Backend Offline';
            sendBtn.disabled = true;
        }
    } catch (error) {
        console.error('Status check failed:', error);
        isBackendOnline = false;
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
