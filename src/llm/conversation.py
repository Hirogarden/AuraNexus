"""Conversation Manager - Handles chat history and persistence."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class Message:
    """Represents a single chat message."""
    
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role  # "user", "assistant", "system"
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        """Create from dictionary."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp")
        )


class ConversationManager:
    """Manages conversation history and persistence."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize conversation manager.
        
        Args:
            data_dir: Directory to store conversation data. If None, uses ./data
        """
        self.data_dir = Path(data_dir or (Path(__file__).parent.parent.parent / "data"))
        self.data_dir.mkdir(exist_ok=True)
        
        self.messages: List[Message] = []
        self.current_session = self._generate_session_id()
        self.system_prompt = "You are a helpful AI assistant."
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation.
        
        Args:
            role: "user" or "assistant"
            content: The message content
        """
        message = Message(role, content)
        self.messages.append(message)
    
    def get_messages_for_api(self) -> List[Dict]:
        """Get messages in format suitable for LLM API.
        
        Returns:
            List of message dicts with 'role' and 'content'
        """
        # Include system prompt at the beginning
        api_messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history
        for msg in self.messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return api_messages
    
    def clear_conversation(self) -> None:
        """Clear the current conversation."""
        self.messages = []
        self.current_session = self._generate_session_id()
    
    def save_conversation(self, filename: Optional[str] = None) -> str:
        """Save conversation to file.
        
        Args:
            filename: Custom filename. If None, uses session ID.
            
        Returns:
            Path to saved file
        """
        filename = filename or f"conversation_{self.current_session}.json"
        filepath = self.data_dir / filename
        
        data = {
            "session_id": self.current_session,
            "timestamp": datetime.now().isoformat(),
            "system_prompt": self.system_prompt,
            "messages": [msg.to_dict() for msg in self.messages],
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def load_conversation(self, filepath: str) -> bool:
        """Load conversation from file.
        
        Args:
            filepath: Path to conversation file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.current_session = data.get("session_id", self._generate_session_id())
            self.system_prompt = data.get("system_prompt", self.system_prompt)
            self.messages = [
                Message.from_dict(msg) for msg in data.get("messages", [])
            ]
            return True
        except Exception as e:
            print(f"Error loading conversation: {e}")
            return False
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get recent saved conversations.
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation info dicts
        """
        json_files = sorted(
            self.data_dir.glob("conversation_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        conversations = []
        for filepath in json_files[:limit]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                conversations.append({
                    "filepath": str(filepath),
                    "timestamp": data.get("timestamp"),
                    "message_count": len(data.get("messages", [])),
                    "filename": filepath.name,
                })
            except Exception:
                continue
        
        return conversations
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt.
        
        Args:
            prompt: The system prompt text
        """
        self.system_prompt = prompt
