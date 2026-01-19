import React from 'react';
import { Heart, BookOpen, Search } from 'lucide-react';
import './Sidebar.css';

const modes = [
  {
    id: 'companion',
    name: 'Companion Mode',
    icon: Heart,
    description: 'Helpful assistant for any task',
    color: 'var(--accent-companion)',
  },
  {
    id: 'youniverse',
    name: "AI 'You'niverse",
    icon: BookOpen,
    description: 'Interactive storytelling & world-building',
    color: 'var(--accent-youniverse)',
  },
];

function Sidebar({ currentMode, onModeChange }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">
          <span className="title-aura">Aura</span>
          <span className="title-nexus">Nexus</span>
        </h1>
        <p className="sidebar-subtitle">AI Companion & Assistant</p>
      </div>
      
      <div className="mode-selector">
        <h2 className="mode-selector-label">Mode Selection</h2>
        
        <div className="mode-list">
          {modes.map((mode) => {
            const Icon = mode.icon;
            const isActive = currentMode === mode.id;
            
            return (
              <button
                key={mode.id}
                className={`mode-button ${isActive ? 'active' : ''}`}
                onClick={() => onModeChange(mode.id)}
                style={{ '--mode-color': mode.color }}
              >
                {mode.id === 'youniverse' ? (
                  <div className="mode-logo">
                    <img src="/youniverse-logo.png" alt="You'niverse" />
                  </div>
                ) : (
                  <div className="mode-icon">
                    <Icon size={20} />
                  </div>
                )}
                
                <div className="mode-info">
                  <span className="mode-name">{mode.name}</span>
                  <span className="mode-description">{mode.description}</span>
                </div>
                
                {isActive && <div className="mode-indicator" />}
              </button>
            );
          })}
        </div>
      </div>
      
      <div className="sidebar-footer">
        <button className="search-button">
          <Search size={18} />
          <span>Search Memory</span>
        </button>
        
        <div className="footer-info">
          <p className="footer-text">
            Private & Secure • Fully Offline
          </p>
          <p className="footer-version">
            Version 1.0.0
          </p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
