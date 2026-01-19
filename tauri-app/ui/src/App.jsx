import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import './styles/App.css';

// Import components (we'll create these next)
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import StatusBar from './components/StatusBar';

function App() {
  // State management
  const [currentMode, setCurrentMode] = useState('companion');
  const [messages, setMessages] = useState([]);
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [modelStatus, setModelStatus] = useState('checking');
  
  // Check backend status on mount
  useEffect(() => {
    async function initializeApp() {
      try {
        setModelStatus('checking');
        const backendReady = await invoke('check_backend');
        
        if (backendReady) {
          setIsBackendReady(true);
          setModelStatus('ready');
          
          // Load current mode
          const mode = await invoke('get_current_mode');
          setCurrentMode(mode.toLowerCase());
          
          // Load conversation history
          const history = await invoke('get_conversation_history', { limit: 50 });
          setMessages(history);
        } else {
          // Need to download and initialize model
          setModelStatus('downloading');
          await invoke('initialize_model');
          setIsBackendReady(true);
          setModelStatus('ready');
        }
      } catch (error) {
        console.error('Failed to initialize:', error);
        setModelStatus('error');
      } finally {
        setIsInitializing(false);
      }
    }
    
    initializeApp();
  }, []);
  
  // Handle mode switching
  const handleModeChange = async (newMode) => {
    try {
      await invoke('switch_mode', { mode: newMode });
      setCurrentMode(newMode);
      setMessages([]); // Clear history when switching modes
    } catch (error) {
      console.error('Failed to switch mode:', error);
    }
  };
  
  // Handle sending messages
  const handleSendMessage = async (messageText) => {
    if (!messageText.trim() || !isBackendReady) return;
    
    // Add user message immediately
    const userMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    
    try {
      // Get AI response
      const response = await invoke('send_chat_message', { 
        message: messageText 
      });
      
      // Add assistant response
      const assistantMessage = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        quality_score: response.quality_score,
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Add error message
      const errorMessage = {
        role: 'system',
        content: `Error: ${error}`,
        timestamp: new Date().toISOString(),
      };
      
      setMessages(prev => [...prev, errorMessage]);
    }
  };
  
  // Loading screen
  if (isInitializing) {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="loading-spinner" />
          <h2>Initializing AuraNexus</h2>
          <p>
            {modelStatus === 'checking' && 'Checking for language model...'}
            {modelStatus === 'downloading' && 'Downloading starter model (this may take a few minutes)...'}
            {modelStatus === 'error' && 'Failed to initialize. Please check the console.'}
          </p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="app" data-mode={currentMode}>
      <Sidebar 
        currentMode={currentMode}
        onModeChange={handleModeChange}
      />
      
      <main className="app-main">
        <ChatWindow 
          messages={messages}
          onSendMessage={handleSendMessage}
          isBackendReady={isBackendReady}
          currentMode={currentMode}
        />
        
        <StatusBar 
          modelStatus={modelStatus}
          currentMode={currentMode}
        />
      </main>
    </div>
  );
}

export default App;
