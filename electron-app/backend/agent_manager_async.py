"""
Agent Manager - Async/Threading Edition
Replaces multiprocessing with asyncio tasks for Windows compatibility
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Message structure for agent communication"""
    type: str
    content: str
    timestamp: str
    sender: Optional[str] = None


class AsyncAgentManager:
    """Manages storytelling agents as async tasks (no multiprocessing)"""
    
    def __init__(self):
        self.agents: Dict[str, 'AsyncAgent'] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.response_queue: asyncio.Queue = asyncio.Queue()
        
        # Generic story agent configs (not DND-specific)
        # use_llm=True to use KoboldCPP, False for rule-based responses
        self.agent_configs = {
            "narrator": {
                "role": "narrator",
                "personality": "descriptive, immersive",
                "use_llm": True,
                "temperature": 0.8,
                "max_tokens": 250
            },
            "character_1": {
                "role": "character",
                "personality": "dynamic, reactive",
                "use_llm": True,
                "temperature": 0.7,
                "max_tokens": 150
            },
            "character_2": {
                "role": "character",
                "personality": "thoughtful, strategic",
                "use_llm": True,
                "temperature": 0.6,
                "max_tokens": 150
            },
            "director": {
                "role": "director",
                "personality": "guides pacing, manages flow",
                "use_llm": True,
                "temperature": 0.5,
                "max_tokens": 200
            }
        }
        self.running = False
    
    async def start_all_agents(self):
        """Start all agent tasks"""
        if self.running:
            logger.warning("Agents already running")
            return
        
        self.running = True
        for name, config in self.agent_configs.items():
            await self.start_agent(name, config)
        
        logger.info(f"Started {len(self.agents)} agents")
    
    async def start_agent(self, name: str, config: dict):
        """Start a single agent task"""
        try:
            self.message_queues[name] = asyncio.Queue()
            
            # Import here to avoid circular imports
            from .agents.async_agent import AsyncAgent
            
            agent = AsyncAgent(
                name=name,
                config=config,
                msg_queue=self.message_queues[name],
                resp_queue=self.response_queue
            )
            
            self.agents[name] = agent
            self.tasks[name] = asyncio.create_task(agent.run())
            
            logger.info(f"Started agent: {name}")
        except Exception as e:
            logger.error(f"Failed to start agent {name}: {e}")
    
    async def stop_all_agents(self):
        """Stop all agent tasks"""
        if not self.running:
            return
        
        self.running = False
        
        # Send stop messages
        for name in list(self.agents.keys()):
            await self.stop_agent(name)
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        
        self.agents.clear()
        self.tasks.clear()
        self.message_queues.clear()
        
        logger.info("Stopped all agents")
    
    async def stop_agent(self, name: str):
        """Stop a specific agent"""
        if name not in self.agents:
            return
        
        try:
            # Send stop signal
            if name in self.message_queues:
                await self.message_queues[name].put(
                    AgentMessage(
                        type="stop",
                        content="",
                        timestamp=datetime.now().isoformat()
                    )
                )
            
            # Wait for task to complete
            if name in self.tasks:
                task = self.tasks[name]
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            logger.info(f"Stopped agent: {name}")
        except Exception as e:
            logger.error(f"Error stopping agent {name}: {e}")
    
    async def restart_agent(self, name: str):
        """Restart a specific agent"""
        if name not in self.agent_configs:
            raise ValueError(f"Unknown agent: {name}")
        
        await self.stop_agent(name)
        await asyncio.sleep(0.5)  # Brief pause
        await self.start_agent(name, self.agent_configs[name])
    
    async def send_message(self, message: str, target_agent: Optional[str] = None) -> dict:
        """Send message to agent and wait for response"""
        if not self.running:
            return {
                "agent": "system",
                "response": "Agent system not running",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            if target_agent is None:
                target_agent = "director"
            
            if target_agent not in self.message_queues:
                raise ValueError(f"Unknown agent: {target_agent}")
            
            # Send message
            await self.message_queues[target_agent].put(
                AgentMessage(
                    type="chat",
                    content=message,
                    timestamp=datetime.now().isoformat()
                )
            )
            
            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(
                    self.response_queue.get(),
                    timeout=30.0
                )
                return response
            except asyncio.TimeoutError:
                return {
                    "agent": target_agent,
                    "response": "Agent is processing... (timeout)",
                    "timestamp": datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "agent": "system",
                "response": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def broadcast_message(self, message: str) -> List[dict]:
        """Send message to all agents and collect responses"""
        if not self.running:
            return []
        
        # Send to all agents
        tasks = []
        for name in self.message_queues.keys():
            tasks.append(self.send_message(message, target_agent=name))
        
        # Wait for all responses
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        return [r for r in responses if isinstance(r, dict)]
    
    def get_agent_status(self) -> dict:
        """Get status of all agents"""
        return {
            name: "running" if (name in self.tasks and not self.tasks[name].done()) else "stopped"
            for name in self.agents.keys()
        }
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.start_all_agents()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.stop_all_agents()
