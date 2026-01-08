"""
Launcher Configuration - Manages launcher settings
"""

import json
from pathlib import Path
from typing import Any


class LauncherConfig:
    """Manages launcher configuration"""
    
    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "updates": {
            "check_on_startup": True,
            "check_launcher": True,
            "check_images": True,
            "auto_install_launcher": True,
            "auto_install_images": False,
            "check_interval_days": 1,
            "channel": "stable"  # stable, beta, nightly
        },
        "launcher": {
            "auto_launch_ui": True,
            "minimize_to_tray": True,
            "start_with_windows": False
        },
        "services": {
            "ollama_url": "http://localhost:11434",
            "web_ui_port": 8000
        }
    }
    
    def __init__(self):
        # Config file location
        self.config_dir = Path.home() / "AppData" / "Local" / "AuraNexus"
        self.config_file = self.config_dir / "launcher_config.json"
        
        # Create config directory if needed
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        self.config = self.load_config()
    
    def load_config(self) -> dict:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                # Merge with defaults (in case new keys were added)
                return self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
                
            except Exception as e:
                print(f"Failed to load config: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create default config
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config: dict = None):
        """Save configuration to file"""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value using dot notation
        Example: get('updates.check_on_startup')
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set config value using dot notation
        Example: set('updates.check_on_startup', True)
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save_config()
    
    def _merge_configs(self, default: dict, loaded: dict) -> dict:
        """Recursively merge loaded config with defaults"""
        result = default.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
