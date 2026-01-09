"""Ollama Service Manager - Automatically start and manage Ollama backend"""

import subprocess
import time
import os
import sys
import requests
from pathlib import Path
from typing import Optional, Tuple

# Import bundle manager for self-contained Ollama
from ollama_bundle_manager import OllamaBundleManager


class OllamaServiceManager:
    """Manages the Ollama service lifecycle with bundled Ollama support"""
    
    def __init__(self, ollama_host: str = "http://localhost:11434", use_bundled: bool = True):
        self.ollama_host = ollama_host
        self.ollama_process: Optional[subprocess.Popen] = None
        self.use_bundled = use_bundled
        
        # Initialize bundle manager
        if use_bundled:
            self.bundle_manager = OllamaBundleManager()
        else:
            self.bundle_manager = None
        
    def is_ollama_installed(self) -> Tuple[bool, Optional[str]]:
        """Check if Ollama is installed and return the path to executable"""
        # If using bundled mode, check bundle first
        if self.use_bundled and self.bundle_manager:
            if self.bundle_manager.is_installed():
                return True, str(self.bundle_manager.get_executable_path())
            
            # Try to install bundled Ollama
            print("Bundled Ollama not found. Attempting to install...")
            success, message = self.bundle_manager.ensure_installed(auto_download=True)
            if success:
                return True, str(self.bundle_manager.get_executable_path())
            else:
                print(f"Failed to install bundled Ollama: {message}")
                # Fall through to check system Ollama
        
        # Check system Ollama as fallback
        possible_paths = [
            # Standard Windows installation
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            # User might have it in PATH
            "ollama",
        ]
        
        for path in possible_paths:
            try:
                if isinstance(path, Path):
                    if path.exists():
                        return True, str(path)
                else:
                    # Check if it's in PATH
                    result = subprocess.run(
                        ["where", "ollama"] if sys.platform == "win32" else ["which", "ollama"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return True, result.stdout.strip().split('\n')[0]
            except Exception:
                continue
                
        return False, None
    
    def is_ollama_running(self) -> bool:
        """Check if Ollama service is already running"""
        try:
            response = requests.get(
                f"{self.ollama_host}/api/tags",
                timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def start_ollama(self) -> Tuple[bool, str]:
        """
        Start Ollama service if not already running
        Returns: (success: bool, message: str)
        """
        # First check if already running
        if self.is_ollama_running():
            return True, "Ollama is already running"
        
        # Check if Ollama is installed
        installed, ollama_path = self.is_ollama_installed()
        if not installed:
            return False, (
                "Ollama is not installed. Please install it from:\n"
                "https://ollama.com/download\n\n"
                "After installation, restart AuraNexus."
            )
        
        # Start Ollama service
        try:
            print(f"Starting Ollama service from: {ollama_path}")
            
            # Get environment variables (bundled mode sets OLLAMA_MODELS, etc.)
            env = os.environ.copy()
            if self.use_bundled and self.bundle_manager:
                env = self.bundle_manager.get_environment()
                print(f"Using bundled models directory: {env.get('OLLAMA_MODELS')}")
            
            # On Windows, use 'ollama serve' in a detached process
            if sys.platform == "win32":
                # Use CREATE_NEW_PROCESS_GROUP to detach
                self.ollama_process = subprocess.Popen(
                    [ollama_path, "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                    close_fds=True
                )
            else:
                self.ollama_process = subprocess.Popen(
                    [ollama_path, "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    start_new_session=True
                )
            
            # Wait for service to be ready (max 30 seconds)
            print("Waiting for Ollama to start...")
            for attempt in range(30):
                time.sleep(1)
                if self.is_ollama_running():
                    print(f"[OK] Ollama started successfully (took {attempt + 1}s)")
                    return True, f"Ollama started successfully"
            
            # Timeout
            return False, "Ollama started but didn't respond within 30 seconds"
            
        except Exception as e:
            return False, f"Failed to start Ollama: {str(e)}"
    
    def stop_ollama(self):
        """Stop the Ollama service if we started it"""
        if self.ollama_process:
            try:
                self.ollama_process.terminate()
                self.ollama_process.wait(timeout=5)
                print("[OK] Ollama service stopped")
            except Exception as e:
                print(f"Warning: Failed to stop Ollama cleanly: {e}")
                try:
                    self.ollama_process.kill()
                except Exception:
                    pass
            finally:
                self.ollama_process = None
    
    def ensure_ollama_running(self) -> Tuple[bool, str]:
        """
        Ensure Ollama is running, starting it if necessary
        Returns: (success: bool, message: str)
        """
        if self.is_ollama_running():
            return True, "Ollama is running"
        
        return self.start_ollama()


def main():
    """Test the service manager"""
    manager = OllamaServiceManager()
    
    print("Checking Ollama installation...")
    installed, path = manager.is_ollama_installed()
    print(f"Installed: {installed}, Path: {path}")
    
    print("\nChecking if Ollama is running...")
    running = manager.is_ollama_running()
    print(f"Running: {running}")
    
    if not running:
        print("\nAttempting to start Ollama...")
        success, message = manager.start_ollama()
        print(f"Result: {message}")


if __name__ == "__main__":
    main()
