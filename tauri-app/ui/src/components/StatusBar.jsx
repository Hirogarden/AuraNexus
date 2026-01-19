import React from 'react';
import { Shield, HardDrive, Wifi, WifiOff } from 'lucide-react';
import './StatusBar.css';

function StatusBar({ modelStatus, currentMode }) {
  const getStatusColor = () => {
    switch (modelStatus) {
      case 'ready': return 'var(--success)';
      case 'downloading': return 'var(--warning)';
      case 'error': return 'var(--error)';
      default: return 'var(--text-tertiary)';
    }
  };
  
  const getStatusText = () => {
    switch (modelStatus) {
      case 'ready': return 'Model Loaded';
      case 'downloading': return 'Downloading Model...';
      case 'checking': return 'Checking...';
      case 'error': return 'Model Error';
      default: return 'Unknown';
    }
  };
  
  return (
    <div className="status-bar">
      <div className="status-section">
        <Shield size={14} />
        <span className="status-label">HIPAA Compliant</span>
      </div>
      
      <div className="status-section">
        <WifiOff size={14} />
        <span className="status-label">Fully Offline</span>
      </div>
      
      <div className="status-section">
        <HardDrive size={14} />
        <span className="status-label" style={{ color: getStatusColor() }}>
          {getStatusText()}
        </span>
      </div>
      
      <div className="status-section">
        <div 
          className="mode-badge"
          style={{ '--badge-color': `var(--accent-${currentMode})` }}
        >
          {currentMode.charAt(0).toUpperCase() + currentMode.slice(1)} Mode
        </div>
      </div>
    </div>
  );
}

export default StatusBar;
