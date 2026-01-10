"""
AuraNexus Core Backend - FastAPI Server
Orchestrates multi-agent storytelling system (async, no multiprocessing)
In-process LLM for HIPAA compliance (no external dependencies)

⚠️ SECURITY NOTICE:
This application is designed for HIPAA compliance and handles Protected Health 
Information (PHI) for mental health support. ALL features must follow:
- No external API calls with PHI
- Encrypt all PHI at rest (AES-256-GCM)
- In-process LLM only (no external servers)
- Audit all PHI access
- See HIPAA_COMPLIANCE.md for full requirements

When adding features, check SECURITY_CHECKLIST.md FIRST.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import os
from typing import Optional, List
from datetime import datetime
from agent_manager_async import AsyncAgentManager
import llm_manager

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

# Initialize async agent manager (no multiprocessing)
agent_manager = AsyncAgentManager()

class ChatRequest(BaseModel):
    message: str
    target_agent: Optional[str] = None

class ChatResponse(BaseModel):
    agent: str
    role: str
    response: str
    timestamp: str

class BroadcastRequest(BaseModel):
    message: str

@app.on_event("startup")
async def startup():
    """Start all agents on server startup"""
    logger.info("Starting AuraNexus backend...")
    
    # Load LLM model into process (if available)
    model_path = os.getenv('MODEL_PATH')
    if model_path:
        logger.info(f"Loading model: {model_path}")
        llm_manager.load_model(model_path)
    else:
        logger.info("Attempting auto-load of model...")
        if not llm_manager.auto_load_model():
            logger.warning("No model loaded - agents will use fallback responses")
            logger.info("To use LLM: Place .gguf model in ./models/ or set MODEL_PATH environment variable")
    
    # Show model info
    model_info = llm_manager.get_model_info()
    if model_info["loaded"]:
        logger.info(f"✅ Model loaded IN-PROCESS (secure, HIPAA-compliant)")
        logger.info(f"   Path: {model_info['model_path']}")
        logger.info(f"   Context: {model_info['context_size']}")
        logger.info(f"   Size: {model_info['model_size_gb']:.2f} GB")
    
    # Start agents
    await agent_manager.start_all_agents()
    logger.info("Backend ready - async agents running!")

@app.on_event("shutdown")
async def shutdown():
    """Clean up agents on shutdown"""
    logger.info("Shutting down agents...")
    await agent_manager.stop_all_agents()
    
    # Unload model from memory
    llm_manager.unload_model()

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
    Send message to specific agent and get response
    """
    try:
        response_data = await agent_manager.send_message(
            message=request.message,
            target_agent=request.target_agent
        )
        
        return ChatResponse(
            agent=response_data["agent"],
            role=response_data.get("role", "unknown"),
            response=response_data["response"],
            timestamp=response_data["timestamp"]
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/broadcast")
async def broadcast(request: BroadcastRequest):
    """
    Broadcast message to all agents and collect responses
    """
    try:
        responses = await agent_manager.broadcast_message(request.message)
        return {
            "message": request.message,
            "responses": responses,
            "count": len(responses)
        }
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def list_agents():
    """Get status of all agents"""
    return agent_manager.get_agent_status()

@app.post("/agents/{agent_name}/restart")
async def restart_agent(agent_name: str):
    """Restart a specific agent"""
    try:
        await agent_manager.restart_agent(agent_name)
        return {"status": "restarted", "agent": agent_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop a specific agent"""
    try:
        await agent_manager.stop_agent(agent_name)
        return {"status": "stopped", "agent": agent_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str):
    """Start a specific agent"""
    try:
        if agent_name not in agent_manager.agent_configs:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
        
        await agent_manager.start_agent(agent_name, agent_manager.agent_configs[agent_name])
        return {"status": "started", "agent": agent_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/model")
async def get_model_status():
    """Get LLM model status"""
    return llm_manager.get_model_info()

@app.post("/model/load")
async def load_model_endpoint(model_path: str):
    """Load a specific model"""
    success = llm_manager.load_model(model_path)
    if success:
        return {"status": "loaded", "info": llm_manager.get_model_info()}
    else:
        raise HTTPException(status_code=500, detail="Failed to load model")

@app.post("/model/unload")
async def unload_model_endpoint():
    """Unload current model"""
    llm_manager.unload_model()
    return {"status": "unloaded"}

if __name__ == "__main__":
    import sys
    port = 8000
    
    # Parse command line args
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    logger.info(f"Starting AuraNexus backend on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
