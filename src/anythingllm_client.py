"""AnythingLLM integration for AuraNexus.
Provides optional connection to external AnythingLLM instance.
"""

import requests
from typing import List, Dict, Optional


class AnythingLLMClient:
    """Client for AnythingLLM RAG system."""
    
    def __init__(self, base_url: str = "http://localhost:3001", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.workspace = "default"
        self.thread_id = None
    
    def is_available(self) -> bool:
        """Check if AnythingLLM is running and accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/v1/system/check", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def set_workspace(self, workspace_name: str):
        """Set the active workspace."""
        self.workspace = workspace_name
    
    def chat(self, message: str, mode: str = "query") -> Dict:
        """Send a chat message to AnythingLLM.
        
        Args:
            message: User message
            mode: 'chat' or 'query' (RAG mode)
            
        Returns:
            Response dict with 'textResponse' and other metadata
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "message": message,
            "mode": mode
        }
        
        if self.thread_id:
            payload["sessionId"] = self.thread_id
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/workspace/{self.workspace}/chat",
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            
            # Update thread ID if provided
            if "sessionId" in data:
                self.thread_id = data["sessionId"]
            
            return data
        except Exception as e:
            return {"error": str(e)}
    
    def add_document(self, content: str, filename: str = "memory.txt") -> bool:
        """Add a document to AnythingLLM workspace.
        
        Args:
            content: Document content
            filename: Document filename
            
        Returns:
            True if successful
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        files = {
            'file': (filename, content, 'text/plain')
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/workspace/{self.workspace}/upload",
                files=files,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return True
        except:
            return False
    
    def get_workspaces(self) -> List[str]:
        """Get list of available workspaces."""
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/workspaces",
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            return [ws.get("name", "") for ws in data.get("workspaces", [])]
        except:
            return []
