import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import './ChatWindow.css';

function ChatWindow({ messages, onSendMessage, isBackendReady, currentMode }) {
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [inputValue]);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!inputValue.trim() || isSending || !isBackendReady) return;
    
    setIsSending(true);
    await onSendMessage(inputValue);
    setInputValue('');
    setIsSending(false);
  };
  
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };
  
  const getModeLabel = () => {
    switch (currentMode) {
      case 'companion': return 'Companion';
      case 'youniverse': return 'You\'niverse';
      default: return 'Assistant';
    }
  };
  
  return (
    <div className="chat-window">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-content">
          <h2 className="chat-title">{getModeLabel()} Mode</h2>
          <div className="chat-status">
            <div className={`status-indicator ${isBackendReady ? 'ready' : 'loading'}`} />
            <span className="status-text">
              {isBackendReady ? 'Ready' : 'Initializing...'}
            </span>
          </div>
        </div>
      </div>
      
      {/* Messages */}
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            {currentMode === 'youniverse' ? (
              <div className="empty-logo">
                <img src="/youniverse-logo.png" alt="You'niverse" style={{ width: '120px', height: '120px', opacity: 0.8 }} />
              </div>
            ) : (
              <div className="empty-icon">💬</div>
            )}
            <h3 className="empty-title">{currentMode === 'youniverse' ? 'Your Universe Awaits' : 'Start a conversation'}</h3>
            <p className="empty-description">
              {currentMode === 'companion' && 'I\'m here to help with any questions, tasks, or conversations you\'d like to have.'}
              {currentMode === 'youniverse' && 'An infinite canvas for storytelling. Create characters, build worlds, and explore limitless possibilities. Your imagination is the only boundary.'}
            </p>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message message-${message.role}`}
                data-role={message.role}
              >
                <div className="message-avatar">
                  {message.role === 'user' ? '👤' : '🤖'}
                </div>
                
                <div className="message-content">
                  <div className="message-header">
                    <span className="message-role">
                      {message.role === 'user' ? 'You' : getModeLabel()}
                    </span>
                    <span className="message-timestamp">
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  
                  <div className="message-text">
                    {message.content}
                  </div>
                  
                  {message.quality_score && (
                    <div className="message-quality">
                      Quality: {(message.quality_score * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>
      
      {/* Input */}
      <form className="chat-input-container" onSubmit={handleSubmit}>
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={
              isBackendReady
                ? 'Type your message... (Shift+Enter for new line)'
                : 'Initializing...'
            }
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!isBackendReady || isSending}
            rows={1}
          />
          
          <button
            type="submit"
            className="send-button"
            disabled={!inputValue.trim() || !isBackendReady || isSending}
          >
            {isSending ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default ChatWindow;
