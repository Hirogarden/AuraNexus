"""
AuraNexus Core Backend - FastAPI Server
Orchestrates multi-agent DND party system
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from typing import Optional
from datetime import datetime
from agent_manager import AgentManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AuraNexus API", version="1.0.0")

# Enable CORS for Electron frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent manager
agent_manager = AgentManager()

class ChatRequest(BaseModel):
    message: str
    target_agent: Optional[str] = None

class ChatResponse(BaseModel):
    agent: str
    response: str
    timestamp: str

@app.on_event("startup")
async def startup():
    """Start all agents on server startup"""
    logger.info("Starting AuraNexus backend...")
    # Skip agent startup for now - Windows multiprocessing issues
    # agent_manager.start_all_agents()
    logger.info("Backend ready (agents disabled temporarily)")

@app.on_event("shutdown")
async def shutdown():
    """Clean up agents on shutdown"""
    logger.info("Shutting down agents...")
    agent_manager.stop_all_agents()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "agents": agent_manager.get_agent_status()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send message to party
    For now, returns simple mock responses
    """
    try:
        # Mock response until agents are fully working
        agent_name = request.target_agent or "dm"
        
        responses = {
            "fighter": f"⚔️ Fighter: Ready for action! '{request.message}'",
            "wizard": f"🧙 Wizard: Interesting... '{request.message}'",
            "cleric": f"✨ Cleric: May light guide us! '{request.message}'",
            "dm": f"🎲 DM: As you say '{request.message}', the party prepares..."
        }
        
        response_text = responses.get(agent_name, f"Echo: {request.message}")
        
        return ChatResponse(
            agent=agent_name,
            response=response_text,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def list_agents():
    """Get status of all agents"""
    return agent_manager.get_agent_status()

@app.post("/agents/{agent_name}/restart")
async def restart_agent(agent_name: str):
    """Restart a specific agent"""
    try:
        agent_manager.restart_agent(agent_name)
        return {"status": "restarted", "agent": agent_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import sys
    port = 8000
    
    # Parse command line args
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    logger.info(f"Starting AuraNexus backend on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
