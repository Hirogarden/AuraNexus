import React from 'react';
import { Heart, Stethoscope, Code2, Search } from 'lucide-react';
import './Sidebar.css';

const modes = [
  {
    id: 'companion',
    name: 'Companion Mode',
    icon: Heart,
    description: 'Empathetic support & mental wellness',
    color: 'var(--accent-companion)',
  },
  {
    id: 'clinical',
    name: 'Clinical Mode',
    icon: Stethoscope,
    description: 'Healthcare documentation & SOAP notes',
    color: 'var(--accent-clinical)',
  },
  {
    id: 'developer',
    name: 'Developer Mode',
    icon: Code2,
    description: 'Testing, metrics & configuration',
    color: 'var(--accent-developer)',
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
        <p className="sidebar-subtitle">AI Healthcare Assistant</p>
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
                <div className="mode-icon">
                  <Icon size={20} />
                </div>
                
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
            HIPAA Compliant • Fully Offline
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
