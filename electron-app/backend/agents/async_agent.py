"""
Async Agent - Story Character
Runs as async task, communicates via asyncio.Queue
No multiprocessing, Windows-compatible
Supports both in-process LLM (secure) and external API (optional)

⚠️ SECURITY: PHI HANDLING
Agents process Protected Health Information (PHI) in mental health conversations.

REQUIREMENTS:
- Use in-process LLM mode (LLM_MODE='inprocess') for HIPAA compliance
- NEVER log user messages or PHI (use placeholders like "***")
- Encrypt conversation history when stored (Phase 2)
- Audit all PHI access (Phase 2)

PROHIBITED:
- External API mode with PHI (use only for non-PHI testing)
- Logging actual message content
- Sending PHI to external services

See SECURITY_CHECKLIST.md before modifying.
"""

import asyncio
import logging
import os
from typing import Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# KoboldCPP configuration (external API mode - optional)
KCPP_URL = os.getenv('KCPP_URL', 'http://127.0.0.1:5001')

# LLM mode: 'inprocess' (default, secure) or 'api' (external KoboldCPP)
LLM_MODE = os.getenv('LLM_MODE', 'inprocess')


class AsyncAgent:
    """Base class for async story agents (no processes)"""
    
    def __init__(
        self,
        name: str,
        config: dict,
        msg_queue: asyncio.Queue,
        resp_queue: asyncio.Queue
    ):
        self.name = name
        self.role = config.get("role", "character")
        self.personality = config.get("personality", "neutral")
        self.msg_queue = msg_queue
        self.resp_queue = resp_queue
        self.running = False
        
        # Memory (integrated with MemoryManager)
        self.use_memory = config.get("use_memory", True)
        self.memory_manager = None
        if self.use_memory:
            try:
                from ..memory_manager import get_memory_manager
                self.memory_manager = get_memory_manager()
                logger.info(f"Agent {name} using memory system")
            except Exception as e:
                logger.warning(f"Agent {name} memory disabled: {e}")
                self.use_memory = False
        
        # Legacy conversation history (fallback if memory disabled)
        self.conversation_history = []
        self.max_history = 20
        
        # LLM settings
        self.use_llm = config.get("use_llm", True)
        self.max_tokens = config.get("max_tokens", 200)
        self.temperature = config.get("temperature", 0.7)
    
    async def run(self):
        """Main agent loop - async task that processes messages"""
        self.running = True
        logger.info(f"Agent {self.name} ({self.role}) starting...")
        
        while self.running:
            try:
                # Wait for message (async, non-blocking)
                msg = await asyncio.wait_for(
                    self.msg_queue.get(),
                    timeout=1.0
                )
                
                if msg.type == "stop":
                    self.running = False
                    break
                
                elif msg.type == "chat":
                    # Extract system_prompt from metadata if provided
                    system_prompt = msg.metadata.get("system_prompt") if hasattr(msg, 'metadata') and msg.metadata else None
                    
                    # Generate response
                    response = await self.generate_response(msg.content, system_prompt=system_prompt)
                    
                    # Send response
                    await self.resp_queue.put({
                        "agent": self.name,
                        "role": self.role,
                        "response": response,
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif msg.type == "update_context":
                    # Update agent's story context
                    self.add_to_history(msg.content)
            
            except asyncio.TimeoutError:
                # No message received, continue waiting
                continue
            
            except Exception as e:
                logger.error(f"Agent {self.name} error: {e}")
                await asyncio.sleep(0.5)
        
        logger.info(f"Agent {self.name} stopped")
    
    def add_to_history(self, message: str):
        """Add message to conversation history"""
        # Use MemoryManager if available
        if self.use_memory and self.memory_manager:
            # Parse role and content
            if ": " in message:
                role_part, content = message.split(": ", 1)
                role = "user" if role_part == "User" else "assistant"
            else:
                role = "assistant"
                content = message
            
            self.memory_manager.add_message(
                role=role,
                content=content,
                metadata={"agent": self.name}
            )
        else:
            # Fallback to legacy history
            self.conversation_history.append({
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
            
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]
    
    async def generate_response(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response to user message
        Uses LLM if available, falls back to rule-based
        """
        # Add to history
        self.add_to_history(f"User: {message}")
        
        # Try LLM first if enabled
        if self.use_llm:
            try:
                response = await self.call_llm(message, system_prompt=system_prompt)
                if response and response != "[LLM response for: " + message + "]":
                    self.add_to_history(f"{self.name}: {response}")
                    return response
            except Exception as e:
                logger.warning(f"LLM call failed for {self.name}: {e}, falling back to rules")
        
        # Fallback to simple rule-based responses
        if self.role == "narrator":
            response = self._narrator_response(message)
        
        elif self.role == "character":
            response = self._character_response(message)
        
        elif self.role == "director":
            response = self._director_response(message)
        
        else:
            response = f"{self.name}: {message}"
        
        # Add response to history
        self.add_to_history(f"{self.name}: {response}")
        
        return response
    
    def _narrator_response(self, message: str) -> str:
        """Generate narrator-style response"""
        # This is placeholder - integrate with KoboldCPP/LLM later
        return f"📖 As {message}, the story unfolds before you. The world feels alive with possibility."
    
    async def call_llm(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Call LLM with message (wrapper for generate_response_with_memory)
        """
        return await self.generate_response_with_memory(message, system_prompt=system_prompt)
    
    async def generate_response_with_memory(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response with memory-augmented context
        Supports both in-process (secure) and API modes
        """
        # Build context from history
        if self.use_memory and self.memory_manager:
            # Get recent conversation from memory manager
            recent_history = self.memory_manager.get_formatted_history(5)
            
            # Get relevant long-term memories (RAG)
            long_term_context = self.memory_manager.get_augmented_context(
                query=prompt,
                n_results=2,
                max_chars=300
            )
            
            context = f"{long_term_context}\n\n{recent_history}" if long_term_context else recent_history
        else:
            # Fallback to legacy history
            context = "\n".join([
                h["content"] for h in self.conversation_history[-5:]
            ])
        
        # Use custom system prompt or fallback to role-specific defaults
        if not system_prompt:
            system_prompts = {
                "narrator": f"You are a descriptive storyteller. Your personality: {self.personality}. Create vivid, immersive descriptions.",
                "character": f"You are {self.name}, a character in the story. Your personality: {self.personality}. Stay in character and respond naturally.",
                "director": f"You are the story director. Your role: {self.personality}. Guide the narrative flow and pacing."
            }
            system_prompt = system_prompts.get(self.role, f"You are {self.name}, a helpful assistant.")
        
        # Build context from history
        context = "\n".join([
            h["content"] for h in self.conversation_history[-5:]
        ])
        
        full_prompt = f"""{system_prompt}

Recent conversation:
{context}

User: {prompt}

{self.name}:"""
        
        # Choose LLM mode
        if LLM_MODE == 'inprocess':
            return await self._call_inprocess_llm(full_prompt)
        else:
            return await self._call_api_llm(full_prompt)
    
    async def _call_inprocess_llm(self, prompt: str) -> str:
        """
        Call in-process LLM (secure, no external dependencies)
        Runs model directly in Python process with role-optimized sampling
        """
        try:
            # Import LLM manager
            import sys
            from pathlib import Path
            backend_path = Path(__file__).parent.parent
            if str(backend_path) not in sys.path:
                sys.path.insert(0, str(backend_path))
            
            from .. import llm_manager
            
            # Check if model is loaded
            if not llm_manager.is_model_loaded():
                raise Exception("No model loaded. Call llm_manager.load_model() or auto_load_model() first")
            
            # Get role-specific sampling preset
            if self.role == "narrator":
                preset = llm_manager.get_sampling_preset("storytelling")
            elif self.role == "character":
                preset = llm_manager.get_sampling_preset("storytelling")
            elif self.role == "director":
                preset = llm_manager.get_sampling_preset("assistant")
            else:
                preset = llm_manager.get_sampling_preset("chat")
            
            # Generate in-process with advanced sampling
            generated = llm_manager.generate(
                prompt=prompt,
                max_tokens=self.max_tokens,
                stop=["\nUser:", "\n\n\n"],
                **preset  # Unpack preset parameters
            )
            
            if not generated:
                raise Exception("Model returned empty response")
            
            # Clean up response
            if generated.startswith(f"{self.name}:"):
                generated = generated[len(self.name)+1:].strip()
            
            return generated
            
        except Exception as e:
            raise Exception(f"In-process LLM error: {str(e)}")
    
    async def _call_api_llm(self, prompt: str) -> str:
        """
        Call external KoboldCPP API (less secure, requires external process)
        Only use this if you need external model hosting
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{KCPP_URL}/api/v1/generate",
                    json={
                        "prompt": prompt,
                        "max_length": self.max_tokens,
                        "temperature": self.temperature,
                        "top_p": 0.9,
                        "top_k": 40,
                        "rep_pen": 1.1,
                        "stop_sequence": ["\nUser:", "\n\n\n"]
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get("results", [{}])[0].get("text", "").strip()
                    
                    # Clean up the response
                    if generated_text:
                        # Remove any prefix of name if LLM included it
                        if generated_text.startswith(f"{self.name}:"):
                            generated_text = generated_text[len(self.name)+1:].strip()
                        
                        return generated_text
                    else:
                        raise Exception("Empty response from LLM")
                else:
                    raise Exception(f"KoboldCPP returned status {response.status_code}")
            
            except httpx.ConnectError:
                raise Exception(f"Cannot connect to KoboldCPP at {KCPP_URL}")
            except httpx.TimeoutException:
                raise Exception("KoboldCPP request timeout")
            except Exception as e:
                raise Exception(f"LLM error: {str(e)}")
