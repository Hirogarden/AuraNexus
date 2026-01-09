"""
Base Agent - DND Party Member
Runs in separate process, communicates via queues
"""

import time
import logging
from multiprocessing import Queue
from datetime import datetime

logger = logging.getLogger(__name__)

class Agent:
    """Base class for all DND party agents"""
    
    def __init__(self, name: str, config: dict, msg_queue: Queue, resp_queue: Queue):
        self.name = name
        self.role = config.get("role", "unknown")
        self.personality = config.get("personality", "neutral")
        self.msg_queue = msg_queue
        self.resp_queue = resp_queue
        self.running = True
    
    def run(self):
        """Main agent loop - processes messages from queue"""
        logger.info(f"Agent {self.name} starting...")
        
        while self.running:
            try:
                # Check for messages (non-blocking)
                if not self.msg_queue.empty():
                    msg = self.msg_queue.get(timeout=0.1)
                    
                    if msg["type"] == "stop":
                        self.running = False
                        break
                    
                    elif msg["type"] == "chat":
                        response = self.generate_response(msg["content"])
                        self.resp_queue.put({
                            "agent": self.name,
                            "response": response,
                            "timestamp": datetime.now().isoformat()
                        })
                
                time.sleep(0.1)  # Prevent busy waiting
                
            except Exception as e:
                logger.error(f"Agent {self.name} error: {e}")
        
        logger.info(f"Agent {self.name} stopped")
    
    def generate_response(self, message: str) -> str:
        """
        Generate response to user message
        Override in subclasses for character-specific behavior
        """
        # Simple rule-based responses for now
        # In production, this would call LLM with character personality
        
        if self.role == "fighter":
            return f"⚔️ Fighter: Let me handle this! {message}"
        
        elif self.role == "wizard":
            return f"🧙 Wizard: *adjusts robes* An interesting problem... {message}"
        
        elif self.role == "cleric":
            return f"✨ Cleric: May the light guide us! {message}"
        
        elif self.role == "dungeon_master":
            return f"🎲 DM: *rolls dice* As you say '{message}', the party awaits your command..."
        
        return f"{self.name}: {message}"
