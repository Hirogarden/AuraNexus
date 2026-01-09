"""
Update Checker - Handles checking and installing updates
"""

import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QThread, Signal


class UpdateChecker(QThread):
    """Background thread for checking and installing updates"""
    
    progress = Signal(str, int, str)  # (message, percentage, details)
    finished = Signal(bool)  # success
    error = Signal(str)  # error message
    
    def __init__(self, config, docker_manager):
        super().__init__()
        self.config = config
        self.docker_manager = docker_manager
        self.github_repo = "yourusername/auranexus"  # TODO: Update with actual repo
        self.current_version = "1.0.0"
    
    def run(self):
        """Main update check flow"""
        try:
            # Step 1: Check launcher updates (if enabled)
            if self.config.get('updates.check_launcher', True):
                self.progress.emit("Checking for launcher updates...", 5, "")
                if self.check_launcher_update():
                    # If launcher updated, it will restart - don't continue
                    return
            
            # Step 2: Check Docker installation
            self.progress.emit("Checking Docker installation...", 15, "")
            if not self.check_docker_installed():
                self.error.emit("Docker Desktop is not running. Please start Docker Desktop and try again.")
                self.finished.emit(False)
                return
            
            # Step 3: Pull required images
            self.progress.emit("Pulling Docker images...", 30, "This may take several minutes for first-time setup")
            try:
                self.docker_manager.pull_images()
            except RuntimeError as e:
                self.error.emit(str(e))
                self.finished.emit(False)
                return
            
            # Step 4: Start services
            self.progress.emit("Starting AuraNexus services...", 70, "")
            try:
                self.docker_manager.start_services()
            except RuntimeError as e:
                self.error.emit(str(e))
                self.finished.emit(False)
                return
            
            # Step 5: Wait for health checks
            self.progress.emit("Waiting for services to be ready...", 85, "")
            if not self.wait_for_health():
                self.error.emit("Services did not start properly")
                self.finished.emit(False)
                return
            
            # Success!
            self.progress.emit("Ready!", 100, "All services are running")
            self.finished.emit(True)
            
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
    
    def check_launcher_update(self) -> bool:
        """
        Check if launcher needs updating
        Returns True if launcher was updated (requires restart)
        """
        try:
            # Check GitHub releases
            url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return False
            
            latest = response.json()
            latest_version = latest['tag_name'].lstrip('v')
            
            if self.compare_versions(latest_version, self.current_version) > 0:
                # New version available
                self.progress.emit(
                    "Launcher update available",
                    10,
                    f"Version {latest_version} is available"
                )
                
                if self.config.get('updates.auto_install_launcher', True):
                    # Download and install
                    return self.update_launcher(latest)
                else:
                    # Just notify
                    self.progress.emit(
                        "Launcher update available",
                        10,
                        f"New version {latest_version} available. Auto-update is disabled."
                    )
            
            return False
            
        except Exception as e:
            print(f"Failed to check launcher updates: {e}")
            return False
    
    def update_launcher(self, release_data: dict) -> bool:
        """
        Download and install launcher update
        Returns True if updated (requires restart)
        """
        try:
            # Find Windows .exe asset
            assets = release_data.get('assets', [])
            exe_asset = next(
                (a for a in assets if a['name'].endswith('.exe')),
                None
            )
            
            if not exe_asset:
                return False
            
            self.progress.emit(
                "Downloading launcher update...",
                10,
                f"Downloading {exe_asset['name']}"
            )
            
            # Download new launcher
            download_url = exe_asset['browser_download_url']
            response = requests.get(download_url, stream=True)
            
            # Save to temp file
            current_exe = sys.executable
            temp_exe = current_exe + ".new"
            
            with open(temp_exe, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Create update script
            update_script = Path(current_exe).parent / "update_launcher.bat"
            
            with open(update_script, 'w') as f:
                f.write(f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{temp_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
""")
            
            # Launch update script and exit
            subprocess.Popen([str(update_script)], shell=True)
            return True
            
        except Exception as e:
            print(f"Failed to update launcher: {e}")
            return False
    
    def check_docker_installed(self) -> bool:
        """Check if Docker Desktop is installed and running"""
        try:
            # Check if Docker is installed
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
            
            # Check if Docker daemon is running
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Docker not installed
            return False
        except subprocess.TimeoutExpired:
            # Docker might be installed but not responding
            return False
        except:
            return False
    
    def install_docker(self) -> bool:
        """Install Docker Desktop"""
        # TODO: Implement Docker Desktop installation
        # This would download and run Docker Desktop installer
        return False
    
    def check_image_updates(self) -> list:
        """Check which Docker images need updates"""
        updates_needed = []
        
        images_to_check = [
            'auranexus-core:latest',
            'auranexus-agent:latest',
            'ollama/ollama:latest'
        ]
        
        for image in images_to_check:
            if self.is_image_update_available(image):
                updates_needed.append(image)
        
        return updates_needed
    
    def is_image_update_available(self, image: str) -> bool:
        """Check if a specific image has updates"""
        try:
            # Get local image digest
            result = subprocess.run(
                ['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                # Image not found locally, needs to be pulled
                return True
            
            local_digest = result.stdout.strip()
            
            # Get remote digest
            result = subprocess.run(
                ['docker', 'manifest', 'inspect', image, '--verbose'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False
            
            # Parse remote digest (simplified)
            # In production, properly parse manifest JSON
            remote_digest = result.stdout[:64]  # Simplified
            
            return local_digest != remote_digest
            
        except:
            return False
    
    def pull_image(self, image: str):
        """Pull a Docker image"""
        try:
            subprocess.run(
                ['docker', 'pull', image],
                capture_output=True,
                timeout=300  # 5 minute timeout
            )
        except Exception as e:
            print(f"Failed to pull {image}: {e}")
    
    def wait_for_health(self) -> bool:
        """Wait for services to be healthy"""
        import time
        
        max_wait = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.get('http://localhost:8000/health', timeout=2)
                if response.status_code == 200:
                    return True
            except:
                pass
            
            time.sleep(2)
        
        return False
    
    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        Compare two version strings
        Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
        """
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        
        for i in range(max(len(parts1), len(parts2))):
            p1 = parts1[i] if i < len(parts1) else 0
            p2 = parts2[i] if i < len(parts2) else 0
            
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        
        return 0
