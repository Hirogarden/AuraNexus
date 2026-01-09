"""Ollama Bundle Manager - Download, install, and manage bundled Ollama

This module ensures AuraNexus has its own isolated Ollama installation
that doesn't interfere with any system-wide Ollama installation.
"""

import os
import sys
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.error


class OllamaBundleManager:
    """Manages bundled Ollama installation within AuraNexus"""
    
    # Ollama download URLs (official releases)
    OLLAMA_URLS = {
        "windows": "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip",
        "linux": "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tgz",
        "darwin": "https://github.com/ollama/ollama/releases/latest/download/ollama-darwin"
    }
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize bundle manager
        
        Args:
            base_dir: Base directory for AuraNexus (defaults to script location)
        """
        if base_dir is None:
            # Get the AuraNexus root directory
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = Path(base_dir)
        self.engines_dir = self.base_dir / "engines"
        self.ollama_dir = self.engines_dir / "ollama"
        self.ollama_bin_dir = self.ollama_dir / "bin"
        self.ollama_models_dir = self.ollama_dir / "models"
        
        # Ensure directories exist
        self.ollama_bin_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_models_dir.mkdir(parents=True, exist_ok=True)
        
        # Platform-specific executable name
        self.platform = sys.platform
        if self.platform == "win32":
            self.ollama_exe = self.ollama_bin_dir / "ollama.exe"
        else:
            self.ollama_exe = self.ollama_bin_dir / "ollama"
    
    def is_installed(self) -> bool:
        """Check if bundled Ollama is installed"""
        return self.ollama_exe.exists() and self.ollama_exe.is_file()
    
    def get_version(self) -> Optional[str]:
        """Get version of installed bundled Ollama"""
        if not self.is_installed():
            return None
        
        try:
            result = subprocess.run(
                [str(self.ollama_exe), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        return None
    
    def download_ollama(self, progress_callback=None) -> Tuple[bool, str]:
        """
        Download Ollama for current platform
        
        Args:
            progress_callback: Optional callback(message: str) for progress updates
            
        Returns:
            (success: bool, message: str)
        """
        def log(msg):
            if progress_callback:
                progress_callback(msg)
            print(msg)
        
        # Determine platform
        platform_key = "windows" if self.platform == "win32" else \
                      "darwin" if self.platform == "darwin" else "linux"
        
        url = self.OLLAMA_URLS.get(platform_key)
        if not url:
            return False, f"Unsupported platform: {self.platform}"
        
        log(f"Downloading Ollama from {url}...")
        
        # Download to temp file
        download_path = self.ollama_dir / "ollama_download.tmp"
        
        try:
            # Download with progress
            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    log(f"Downloading Ollama... {percent}%")
            
            urllib.request.urlretrieve(url, download_path, reporthook=reporthook)
            log("Download complete!")
            
            # Extract/install based on platform
            if platform_key == "windows":
                return self._install_windows(download_path, log)
            else:
                return self._install_unix(download_path, log)
                
        except urllib.error.URLError as e:
            return False, f"Download failed: {e}"
        except Exception as e:
            return False, f"Installation failed: {e}"
        finally:
            # Clean up download
            if download_path.exists():
                download_path.unlink()
    
    def _install_windows(self, zip_path: Path, log_func) -> Tuple[bool, str]:
        """Install Ollama on Windows from zip file"""
        log_func("Extracting Ollama...")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extract to bin directory
                zip_ref.extractall(self.ollama_bin_dir)
            
            # Verify executable exists
            if not self.ollama_exe.exists():
                # Sometimes it extracts to a subdirectory
                for exe_path in self.ollama_bin_dir.rglob("ollama.exe"):
                    shutil.move(str(exe_path), str(self.ollama_exe))
                    break
            
            if self.ollama_exe.exists():
                log_func("✓ Ollama installed successfully!")
                return True, "Ollama installed successfully"
            else:
                return False, "Could not find ollama.exe after extraction"
                
        except Exception as e:
            return False, f"Extraction failed: {e}"
    
    def _install_unix(self, archive_path: Path, log_func) -> Tuple[bool, str]:
        """Install Ollama on Linux/macOS"""
        log_func("Installing Ollama...")
        
        try:
            if self.platform == "darwin":
                # macOS: direct binary download
                shutil.move(str(archive_path), str(self.ollama_exe))
            else:
                # Linux: extract tar.gz
                import tarfile
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(self.ollama_bin_dir)
                
                # Find and move the binary
                for exe_path in self.ollama_bin_dir.rglob("ollama"):
                    if exe_path.is_file() and os.access(exe_path, os.X_OK):
                        shutil.move(str(exe_path), str(self.ollama_exe))
                        break
            
            # Make executable
            self.ollama_exe.chmod(0o755)
            
            if self.ollama_exe.exists():
                log_func("✓ Ollama installed successfully!")
                return True, "Ollama installed successfully"
            else:
                return False, "Could not find ollama binary after extraction"
                
        except Exception as e:
            return False, f"Installation failed: {e}"
    
    def ensure_installed(self, auto_download: bool = True) -> Tuple[bool, str]:
        """
        Ensure Ollama is installed, downloading if necessary
        
        Args:
            auto_download: Whether to automatically download if not installed
            
        Returns:
            (success: bool, message: str)
        """
        if self.is_installed():
            version = self.get_version()
            return True, f"Ollama is installed (version: {version or 'unknown'})"
        
        if not auto_download:
            return False, "Ollama is not installed"
        
        print("Bundled Ollama not found. Downloading...")
        return self.download_ollama()
    
    def get_executable_path(self) -> Optional[Path]:
        """Get path to bundled Ollama executable"""
        if self.is_installed():
            return self.ollama_exe
        return None
    
    def get_models_dir(self) -> Path:
        """Get path to bundled models directory"""
        return self.ollama_models_dir
    
    def get_environment(self) -> dict:
        """
        Get environment variables for running bundled Ollama
        
        Returns:
            Dictionary of environment variables to set
        """
        env = os.environ.copy()
        
        # Set Ollama to use our bundled directories
        env["OLLAMA_MODELS"] = str(self.ollama_models_dir)
        env["OLLAMA_HOST"] = "127.0.0.1:11434"  # Localhost only
        
        # Add bin directory to PATH
        path_var = env.get("PATH", "")
        bin_dir_str = str(self.ollama_bin_dir)
        if bin_dir_str not in path_var:
            env["PATH"] = f"{bin_dir_str}{os.pathsep}{path_var}"
        
        return env


def main():
    """Test the bundle manager"""
    manager = OllamaBundleManager()
    
    print("AuraNexus Ollama Bundle Manager")
    print("=" * 50)
    print(f"Base directory: {manager.base_dir}")
    print(f"Ollama directory: {manager.ollama_dir}")
    print(f"Ollama executable: {manager.ollama_exe}")
    print(f"Models directory: {manager.ollama_models_dir}")
    print()
    
    if manager.is_installed():
        version = manager.get_version()
        print(f"✓ Bundled Ollama is installed")
        print(f"  Version: {version or 'unknown'}")
    else:
        print("✗ Bundled Ollama is not installed")
        print()
        response = input("Download and install Ollama? (y/n): ")
        if response.lower() == 'y':
            success, message = manager.download_ollama()
            print(message)


if __name__ == "__main__":
    main()
