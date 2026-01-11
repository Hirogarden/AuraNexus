"""
Agent Manager - Spawns and manages agent threads
Replaces Docker container orchestration with threading
"""

import threading
from queue import Queue
import time
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages DND party agents as separate threads"""
    
    def __init__(self):
        self.agents: Dict[str, threading.Thread] = {}
        self.message_queues: Dict[str, Queue] = {}
        self.response_queue = Queue()
        
        # Define storytelling agents (generic, user-customizable)
        self.agent_configs = {
            "character_1": {"role": "character", "name": "Character 1", "personality": "brave, action-oriented"},
            "character_2": {"role": "character", "name": "Character 2", "personality": "wise, analytical"},
            "character_3": {"role": "character", "name": "Character 3", "personality": "caring, supportive"},
            "narrator": {"role": "narrator", "name": "Narrator", "personality": "descriptive, immersive"}
        }
    
    def start_all_agents(self):
        """Start all agent processes"""
        for name, config in self.agent_configs.items():
            self.start_agent(name, config)
        time.sleep(1)
    
    def start_agent(self, name: str, config: dict):
        """Start a single agent thread"""
        try:
            self.message_queues[name] = Queue()
            from agents.base_agent import Agent
            thread = threading.Thread(
                target=self._run_agent,
                args=(name, config, self.message_queues[name], self.response_queue),
                daemon=True
            )
            thread.start()
            self.agents[name] = thread
            logger.info(f"Started agent: {name}")
        except Exception as e:
            logger.error(f"Failed to start agent {name}: {e}")
    
    def _run_agent(self, name: str, config: dict, msg_queue: Queue, resp_queue: Queue):
        """Agent thread main loop"""
        from agents.base_agent import Agent
        agent = Agent(name, config, msg_queue, resp_queue)
        agent.run()
    
    def stop_all_agents(self):
        """Stop all agent threads"""
        for name, thread in self.agents.items():
            try:
                if name in self.message_queues:
                    self.message_queues[name].put({"type": "stop"})
                thread.join(timeout=5)
                logger.info(f"Stopped agent: {name}")
            except Exception as e:
                logger.error(f"Error stopping agent {name}: {e}")
    
    def restart_agent(self, name: str):
        """Restart a specific agent"""
        if name not in self.agent_configs:
            raise ValueError(f"Unknown agent: {name}")
        if name in self.agents:
            thread = self.agents[name]
            if thread.is_alive():
                # Signal thread to stop
                if name in self.message_queues:
                    self.message_queues[name].put({"type": "stop"})
                thread.join(timeout=2)
        self.start_agent(name, self.agent_configs[name])
    
    async def process_message(self, message: str, target_agent: Optional[str] = None):
        """Process incoming message"""
        try:
            if target_agent is None:
                target_agent = "dm"
            if target_agent not in self.message_queues:
                raise ValueError(f"Unknown agent: {target_agent}")
            
            self.message_queues[target_agent].put({
                "type": "chat",
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
            
            import asyncio
            start = time.time()
            while time.time() - start < 10:
                if not self.response_queue.empty():
                    return self.response_queue.get()
                await asyncio.sleep(0.1)
            
            return {
                "agent": target_agent,
                "response": "Agent is thinking... (timeout)",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "agent": "system",
                "response": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_agent_status(self) -> dict:
        """Get status of all agents"""
        return {
            name: "running" if thread.is_alive() else "stopped"
            for name, thread in self.agents.items()
        }
