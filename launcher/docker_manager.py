"""
Docker Manager - Handles Docker Compose operations
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import Optional


class DockerManager:
    """Manages Docker Compose services"""
    
    def __init__(self):
        # Get project root (parent of launcher directory when running as script)
        # When frozen by PyInstaller, __file__ doesn't exist in the same way
        if getattr(sys, 'frozen', False):
            # Running as compiled executable in dist/ folder
            # Go up one level to find project root
            exe_dir = Path(sys.executable).parent
            if exe_dir.name == 'dist':
                self.project_root = exe_dir.parent
            else:
                self.project_root = exe_dir
        else:
            # Running as script
            self.project_root = Path(__file__).parent.parent
        self.compose_file = self.project_root / "docker-compose.yml"
    
    def start_services(self) -> bool:
        """Start all Docker services"""
        try:
            # Check if docker-compose.yml exists
            if not self.compose_file.exists():
                raise FileNotFoundError(f"docker-compose.yml not found at {self.compose_file}")
            
            # Increased timeout for image pulling (10 minutes)
            result = subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(f"Docker Compose failed: {error_msg}")
            
            return True
            
        except FileNotFoundError as e:
            raise RuntimeError(str(e))
        except subprocess.TimeoutExpired:
            raise RuntimeError("Docker Compose startup timed out after 120 seconds")
        except Exception as e:
            raise RuntimeError(f"Failed to start services: {e}")
    
    def stop_services(self) -> bool:
        """Stop all Docker services"""
        try:
            result = subprocess.run(
                ['docker-compose', 'down'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Failed to stop services: {e}")
            return False
    
    def restart_services(self) -> bool:
        """Restart all Docker services"""
        try:
            result = subprocess.run(
                ['docker-compose', 'restart'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Failed to restart services: {e}")
            return False
    
    def get_service_status(self) -> dict:
        """Get status of all services"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '--format', 'json'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                services = json.loads(result.stdout)
                return {svc['Service']: svc['State'] for svc in services}
            
            return {}
            
        except Exception as e:
            print(f"Failed to get service status: {e}")
            return {}
    
    def get_logs(self, service: Optional[str] = None, lines: int = 100) -> str:
        """Get logs from services"""
        try:
            cmd = ['docker-compose', 'logs', '--tail', str(lines)]
            if service:
                cmd.append(service)
            
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.stdout
            
        except Exception as e:
            return f"Failed to get logs: {e}"
    
    def is_docker_running(self) -> bool:
        """Check if Docker daemon is running"""
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def pull_images(self) -> bool:
        """Pull all images defined in docker-compose.yml"""
        try:
            result = subprocess.run(
                ['docker-compose', 'pull'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes for pulling images
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(f"Failed to pull images: {error_msg}")
            
            return True
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Image pull timed out after 10 minutes")
        except Exception as e:
            raise RuntimeError(f"Failed to pull images: {e}")
