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
      case 'clinical': return 'Clinical';
      case 'developer': return 'Developer';
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
            <div className="empty-icon">💬</div>
            <h3 className="empty-title">Start a conversation</h3>
            <p className="empty-description">
              {currentMode === 'companion' && 'Share your thoughts and feelings. I\'m here to listen and support you.'}
              {currentMode === 'clinical' && 'Begin documenting patient information, creating notes, or reviewing records.'}
              {currentMode === 'developer' && 'Test features, review metrics, or configure system settings.'}
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
