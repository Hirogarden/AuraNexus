"""
Ollama Server Manager
Automatically starts, stops, and monitors the Ollama server process.
"""

import os
import subprocess
import time
import requests
import psutil
from pathlib import Path
from typing import Optional


class OllamaManager:
    """Manages the Ollama server lifecycle."""
    
    def __init__(self, ollama_path: Optional[str] = None):
        """
        Initialize Ollama manager.
        
        Args:
            ollama_path: Path to ollama.exe. If None, searches common locations.
        """
        self.ollama_path = ollama_path or self._find_ollama()
        self.process: Optional[subprocess.Popen] = None
        self.host = "http://localhost:11434"
        
    def _find_ollama(self) -> Optional[str]:
        """Find ollama.exe in common locations."""
        # Check bundled location (for packaged app)
        bundled = Path(__file__).parent.parent / "bin" / "ollama.exe"
        if bundled.exists():
            return str(bundled)
        
        # Check if ollama is in PATH
        try:
            result = subprocess.run(
                ["where", "ollama"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                if paths:
                    return paths[0].strip()
        except Exception:
            pass
        
        # Check default installation paths
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path("C:/Program Files/Ollama/ollama.exe"),
            Path("C:/Program Files (x86)/Ollama/ollama.exe"),
        ]
        
        for path in common_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def is_running(self) -> bool:
        """Check if Ollama server is already running."""
        try:
            response = requests.get(f"{self.host}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def start(self) -> bool:
        """
        Start the Ollama server.
        
        Returns:
            True if started successfully, False otherwise
        """
        # Check if already running
        if self.is_running():
            print("✓ Ollama server is already running")
            return True
        
        if not self.ollama_path:
            print("\n⚠️  ERROR: Ollama not found!")
            print("Please install Ollama from https://ollama.com")
            print("\nSearched locations:")
            print("  - Bundled: bin/ollama.exe")
            print("  - System PATH")
            print("  - Default install paths")
            return False
        
        if not Path(self.ollama_path).exists():
            print(f"⚠️  ERROR: Ollama not found at {self.ollama_path}")
            return False
        
        try:
            # Start ollama serve in background
            print(f"Starting Ollama server...")
            print(f"  Executable: {self.ollama_path}")
            
            # Create startup info to hide console window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.process = subprocess.Popen(
                [self.ollama_path, "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Wait for server to be ready
            print("  Waiting for server to start", end="", flush=True)
            for i in range(30):  # 30 second timeout
                if self.is_running():
                    print()  # New line after dots
                    print("✓ Ollama server started successfully")
                    return True
                print(".", end="", flush=True)
                time.sleep(1)
            
            print()  # New line after dots
            print("⚠️  ERROR: Ollama server failed to start within 30 seconds")
            
            # Try to get error output
            if self.process and self.process.poll() is not None:
                _, stderr = self.process.communicate(timeout=1)
                if stderr:
                    print(f"Server error: {stderr.decode()}")
            
            return False
            
        except Exception as e:
            print(f"⚠️  ERROR: Failed to start Ollama server: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop(self):
        """Stop the Ollama server if we started it."""
        if self.process:
            try:
                print("Stopping Ollama server...")
                # Terminate the process
                self.process.terminate()
                
                # Wait up to 5 seconds for clean shutdown
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    self.process.kill()
                    self.process.wait()
                
                print("Ollama server stopped")
            except Exception as e:
                print(f"Error stopping Ollama server: {e}")
            finally:
                self.process = None
    
    def kill_existing_servers(self):
        """Kill any existing ollama serve processes (use with caution)."""
        killed = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'serve' in cmdline:
                            proc.kill()
                            killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            print(f"Error killing existing servers: {e}")
        
        if killed > 0:
            print(f"Killed {killed} existing Ollama server(s)")
            time.sleep(2)  # Give OS time to clean up
    
    def restart(self):
        """Restart the Ollama server."""
        print("Restarting Ollama server...")
        self.stop()
        time.sleep(2)  # Give time for cleanup
        return self.start()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
