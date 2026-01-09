"""
Agent Runtime - Lightweight container entrypoint for individual DND characters

This module runs inside each agent container (agent-fighter, agent-wizard, etc.)
and handles:
- Loading character configuration from YAML
- Connecting to Ollama/KoboldCPP backends by container name
- Communicating with core-app for coordination
- Processing chat requests with character personality
"""

import os
import sys
import yaml
import json
import time
import logging
from typing import Dict, Optional, Any
from pathlib import Path

# These will import from the mounted src directory
try:
    from ollama_client import OllamaClient
    from time_utils import get_timestamp
except ImportError:
    # Fallback for development/testing
    sys.path.insert(0, os.path.dirname(__file__))
    from ollama_client import OllamaClient
    from time_utils import get_timestamp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentCharacter:
    """Represents a DND character agent running in a container"""
    
    def __init__(self, config_path: str):
        """
        Initialize agent from character YAML config
        
        Args:
            config_path: Path to character.yaml file (e.g., /app/character.yaml)
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # Environment variables set by docker-compose
        self.agent_name = os.getenv("AGENT_NAME", "unknown")
        self.agent_role = os.getenv("AGENT_ROLE", "character")
        
        # Service URLs (using container names for DNS resolution)
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.koboldcpp_url = os.getenv("KOBOLDCPP_BASE_URL", "http://koboldcpp:5001")
        self.core_app_url = os.getenv("CORE_APP_URL", "http://core-app:8000")
        
        # Initialize LLM clients
        self.ollama_client = OllamaClient(host=self.ollama_url)
        
        logger.info(f"Agent '{self.agent_name}' ({self.agent_role}) initialized")
        logger.info(f"Character: {self.config.get('name', 'Unnamed')}")
        logger.info(f"Ollama backend: {self.ollama_url}")
        logger.info(f"Core app: {self.core_app_url}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load character configuration from YAML"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded character config from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Character config not found: {self.config_path}")
            # Return default config
            return {
                "name": "Default Character",
                "class": "Fighter",
                "personality": "A brave adventurer",
                "model": "llama3.2",
                "system_prompt": "You are a helpful D&D character."
            }
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def get_system_prompt(self) -> str:
        """Build system prompt from character config"""
        character_name = self.config.get('name', 'Unknown')
        character_class = self.config.get('class', 'Adventurer')
        personality = self.config.get('personality', 'A mysterious character')
        
        # Base system prompt
        system_prompt = self.config.get('system_prompt', '')
        
        # Enhance with character details
        enhanced_prompt = f"""You are {character_name}, a {character_class}.

Personality: {personality}

{system_prompt}

Stay in character at all times. Respond as {character_name} would, using their knowledge, skills, and personality traits."""
        
        return enhanced_prompt
    
    def chat(self, user_message: str, context: Optional[list] = None) -> str:
        """
        Process a chat message using the character's personality
        
        Args:
            user_message: User's input message
            context: Optional conversation history
            
        Returns:
            Character's response
        """
        try:
            # Build messages array
            messages = []
            
            # Add system prompt
            messages.append({
                "role": "system",
                "content": self.get_system_prompt()
            })
            
            # Add context if provided
            if context:
                messages.extend(context)
            
            # Add user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Get model from config
            model = self.config.get('model', 'llama3.2')
            
            logger.info(f"[{self.agent_name}] Processing message with model {model}")
            
            # Call Ollama API
            response = self.ollama_client.chat(
                model=model,
                messages=messages
            )
            
            # Extract response text
            assistant_message = response.get('message', {}).get('content', '')
            
            logger.info(f"[{self.agent_name}] Generated response ({len(assistant_message)} chars)")
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"[{self.agent_name} seems distracted and doesn't respond]"
    
    def notify_core_app(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Send event notification to core app
        
        Args:
            event_type: Type of event (e.g., "ready", "response", "handoff_request")
            data: Event data payload
            
        Returns:
            True if notification successful
        """
        try:
            import requests
            
            payload = {
                "agent": self.agent_name,
                "role": self.agent_role,
                "event": event_type,
                "timestamp": get_timestamp(),
                "data": data
            }
            
            response = requests.post(
                f"{self.core_app_url}/api/agent/event",
                json=payload,
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"Failed to notify core app: {e}")
            return False
    
    def run_standalone_mode(self):
        """
        Run agent in standalone interactive mode (for testing)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Agent: {self.config.get('name', 'Unknown')}")
        logger.info(f"Class: {self.config.get('class', 'Unknown')}")
        logger.info(f"Role: {self.agent_role}")
        logger.info(f"{'='*60}\n")
        
        print(f"Hello! I am {self.config.get('name', 'Unknown')}.")
        print("Type 'exit' to quit.\n")
        
        conversation = []
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print(f"{self.config.get('name')}: Farewell, adventurer!")
                    break
                
                if not user_input:
                    continue
                
                # Get response
                response = self.chat(user_input, context=conversation)
                
                # Update conversation history
                conversation.append({"role": "user", "content": user_input})
                conversation.append({"role": "assistant", "content": response})
                
                # Keep last 10 messages to manage context length
                if len(conversation) > 20:
                    conversation = conversation[-20:]
                
                print(f"\n{self.config.get('name')}: {response}\n")
                
            except KeyboardInterrupt:
                print(f"\n{self.config.get('name')}: Farewell!")
                break
            except Exception as e:
                logger.error(f"Error in standalone mode: {e}")
                continue
    
    def run_service_mode(self):
        """
        Run agent as a service waiting for requests from core app
        (Future implementation: FastAPI/Flask server listening on port 8000)
        """
        logger.info("Service mode not yet implemented")
        logger.info("Falling back to standalone mode for testing")
        self.run_standalone_mode()


def main():
    """Main entrypoint for agent container"""
    
    # Get character config path from environment
    config_path = os.getenv("CHARACTER_CONFIG", "/app/character.yaml")
    
    # Check if config exists
    if not Path(config_path).exists():
        logger.error(f"Character config not found: {config_path}")
        logger.error("Container is misconfigured. Check volume mounts in docker-compose.yml")
        sys.exit(1)
    
    # Initialize agent
    agent = AgentCharacter(config_path)
    
    # Notify core app that agent is ready
    agent.notify_core_app("ready", {
        "name": agent.config.get('name'),
        "class": agent.config.get('class'),
        "model": agent.config.get('model')
    })
    
    # Run in appropriate mode
    run_mode = os.getenv("RUN_MODE", "standalone")
    
    if run_mode == "service":
        agent.run_service_mode()
    else:
        agent.run_standalone_mode()


if __name__ == "__main__":
    main()
