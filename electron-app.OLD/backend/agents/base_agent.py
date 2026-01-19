"""
Base Agent - DND Party Member
Runs in separate thread, communicates via queues
"""

import time
import logging
from queue import Queue
from datetime import datetime

logger = logging.getLogger(__name__)

class Agent:
    """Base class for all DND party agents"""
    
    def __init__(self, name: str, config: dict, msg_queue: Queue, resp_queue: Queue):
        self.name = config.get("name", name)  # Use configured name or fallback to key
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
        Generate response to user message using IN-PROCESS LLM (no external services)
        """
        try:
            # Import the in-process LLM manager
            import sys
            sys.path.insert(0, '..')
            from llm_manager import get_llm_instance
            
            # Define personality system prompts
            personalities = {
                "character": f"You are {self.name}, a character in an interactive story. Personality: {self.personality}. Stay in character and respond naturally. Keep responses brief (1-2 sentences).",
                "narrator": f"You are the Narrator. You describe the story world, set scenes, and guide the narrative. Personality: {self.personality}. Keep responses brief (2-3 sentences) and engaging."
            }
            
            # Emojis for each role
            emojis = {
                "character": "💬",
                "narrator": "📖"
            }
            
            system_prompt = personalities.get(self.role, "You are a helpful D&D character.")
            emoji = emojis.get(self.role, "👤")
            
            # Get the shared LLM instance (loaded once, used by all agents)
            llm = get_llm_instance()
            
            if llm is None:
                logger.warning("LLM not loaded yet, using fallback responses")
                return self._fallback_response(emoji)
            
            # Generate response using in-process LLM
            prompt = f"{system_prompt}\n\nPlayer: {message}\n\n{self.name}:"
            
            result = llm(
                prompt,
                max_tokens=100,
                temperature=0.8,
                top_p=0.9,
                stop=["\nPlayer:", "\nUser:", "\n\n"],
                echo=False
            )
            
            llm_response = result['choices'][0]['text'].strip()
            return f"{emoji} {self.name}: {llm_response}"
                
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return self._fallback_response(emojis.get(self.role, "👤"))
    
    def _fallback_response(self, emoji: str) -> str:
        """Fallback responses when LLM not available"""
        if self.role == "character":
            return f"{emoji} {self.name}: I'm ready to continue the story."
        elif self.role == "narrator":
            return f"{emoji} {self.name}: The story unfolds before you..."
        return f"{emoji} {self.name}: *processing...*"
