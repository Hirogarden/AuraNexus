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
from .agent_manager_async import AsyncAgentManager
from . import llm_manager
from .memory_manager import get_memory_manager
from .hierarchical_memory import (
    get_session_manager,
    ProjectType,
    MemoryLayer
)

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
    session_id: Optional[str] = None
    conversation_type: Optional[str] = None  # "peer_support", "medical_assistant", "story", "general"
    encryption_key: Optional[str] = None
    system_prompt: Optional[str] = None

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
        logger.info("🔍 Searching for LLM model...")
        logger.info("💡 First time? A small model (~350MB) will download automatically")
        logger.info("   so you can try AuraNexus right away!")
        
        if not llm_manager.auto_load_model():
            logger.warning("No model available - agents will use fallback responses")
            logger.info("💡 Download failed? Manually place a .gguf model in ./models/")
            logger.info("   See electron-app/models/README.md for recommendations")
    
    # Show model info
    model_info = llm_manager.get_model_info()
    if model_info["loaded"]:
        logger.info(f"✅ Model loaded IN-PROCESS (secure, HIPAA-compliant)")
        logger.info(f"   Path: {model_info['model_path']}")
        logger.info(f"   Context: {model_info['context_size']}")
        logger.info(f"   Size: {model_info['model_size_gb']:.2f} GB")
    
    # Start agents
    await agent_manager.start_all_agents()
    logger.info("Backend ready - async agents running with hierarchical memory!")

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
    Uses hierarchical memory with automatic session management
    """
    try:
        # Get or create session
        session_mgr = get_session_manager()
        
        # Determine session ID and type
        session_id = request.session_id or "default_chat"
        conv_type = request.conversation_type or "general"
        
        # Map conversation type to ProjectType
        type_mapping = {
            "peer_support": ProjectType.MEDICAL_PEER,
            "medical_assistant": ProjectType.MEDICAL_ASSISTANT,
            "story": ProjectType.STORYTELLING,
            "general": ProjectType.GENERAL_CHAT
        }
        project_type = type_mapping.get(conv_type, ProjectType.GENERAL_CHAT)
        
        # Get or create session
        session = session_mgr.get_session(session_id)
        if not session:
            # Auto-create session
            logger.info(f"Creating new session: {session_id} ({conv_type})")
            session = session_mgr.create_session(
                session_id=session_id,
                project_type=project_type,
                encryption_key=request.encryption_key
            )
        
        # Add user message to memory
        session.add_message(
            content=request.message,
            role="user",
            metadata={"agent": request.target_agent or "user"}
        )
        
        # Get agent response
        response_data = await agent_manager.send_message(
            message=request.message,
            target_agent=request.target_agent,
            system_prompt=request.system_prompt
        )
        
        # Add agent response to memory
        session.add_message(
            content=response_data["response"],
            role="assistant",
            metadata={
                "agent": response_data["agent"],
                "role": response_data.get("role", "unknown")
            }
        )
        
        return ChatResponse(
            agent=response_data["agent"],
            role=response_data.get("role", "unknown"),
            response=response_data["response"],
            timestamp=response_data["timestamp"]
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
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

# ===== Memory Management Endpoints =====

@app.get("/memory/stats")
async def get_memory_stats(session_id: str = "default_chat"):
    """Get memory system statistics for a session"""
    try:
        session_mgr = get_session_manager()
        session = session_mgr.get_session(session_id)
        if not session:
            return {
                "error": "Session not found",
                "session_id": session_id,
                "available_sessions": [s["session_id"] for s in session_mgr.list_sessions()]
            }
        return session.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/recent")
async def get_recent_memory(session_id: str = "default_chat", n: int = 10):
    """Get recent conversation history from active memory"""
    try:
        session_mgr = get_session_manager()
        session = session_mgr.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Get recent messages from active memory
        messages = session.active_memory[-n:]
        return {
            "session_id": session_id,
            "messages": messages,
            "count": len(messages),
            "total_active": len(session.active_memory)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MemoryQueryRequest(BaseModel):
    query: str
    n_results: int = 3

class MemoryQueryRequestNew(BaseModel):
    query: str
    session_id: str = "default_chat"
    n_results: int = 3
    layers: Optional[List[str]] = None  # e.g., ["medium_term", "long_term"]

@app.post("/memory/query")
async def query_memory(request: MemoryQueryRequestNew):
    """Query hierarchical memory for relevant context"""
    try:
        session_mgr = get_session_manager()
        session = session_mgr.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        
        # Map string layer names to MemoryLayer enum
        layers = None
        if request.layers:
            layer_map = {
                "active": MemoryLayer.ACTIVE,
                "short_term": MemoryLayer.SHORT_TERM,
                "medium_term": MemoryLayer.MEDIUM_TERM,
                "long_term": MemoryLayer.LONG_TERM,
                "archived": MemoryLayer.ARCHIVED
            }
            layers = [layer_map[l] for l in request.layers if l in layer_map]
        
        results = session.query_memory(
            query=request.query,
            layers=layers,
            n_results=request.n_results
        )
        return {
            "session_id": request.session_id,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateSessionRequest(BaseModel):
    session_id: str
    project_type: str  # "medical_peer", "medical_assistant", "story", "general_chat"
    encryption_key: Optional[str] = None

@app.get("/memory/context")
async def get_memory_context(session_id: str = "default_chat", n: int = 10):
    """Get formatted recent context for LLM prompts"""
    try:
        session_mgr = get_session_manager()
        session = session_mgr.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        context = session.get_recent_context(n)
        return {
            "session_id": session_id,
            "context": context,
            "message_count": n
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/create")
async def create_memory_session(request: CreateSessionRequest):
    """Create new memory session (story, medical project, etc.)"""
    try:
        session_mgr = get_session_manager()
        project_type = ProjectType(request.project_type)
        
        memory = session_mgr.create_session(
            session_id=request.session_id,
            project_type=project_type,
            encryption_key=request.encryption_key
        )
        
        return {
            "status": "created",
            "session_id": request.session_id,
            "stats": memory.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/list")
async def list_sessions():
    """List all memory sessions"""
    try:
        session_mgr = get_session_manager()
        return {"sessions": session_mgr.list_sessions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SwitchSessionRequest(BaseModel):
    session_id: str

@app.post("/sessions/switch")
async def switch_session(request: SwitchSessionRequest):
    """Switch active session"""
    try:
        session_mgr = get_session_manager()
        session_mgr.switch_session(request.session_id)
        return {"status": "switched", "session_id": request.session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get session statistics"""
    try:
        session_mgr = get_session_manager()
        memory = session_mgr.get_session(session_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Session not found")
        return memory.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateBookmarkRequest(BaseModel):
    session_id: str
    label: str
    description: str
    tags: Optional[List[str]] = []
    importance: float = 0.5

@app.post("/sessions/{session_id}/bookmark")
async def create_bookmark(session_id: str, request: CreateBookmarkRequest):
    """Create bookmark in session"""
    try:
        session_mgr = get_session_manager()
        memory = session_mgr.get_session(session_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Session not found")
        
        bookmark_id = memory.create_bookmark(
            label=request.label,
            description=request.description,
            tags=request.tags,
            importance=request.importance
        )
        
        return {
            "status": "created",
            "bookmark_id": bookmark_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/bookmarks")
async def get_bookmarks(session_id: str):
    """Get all bookmarks for session"""
    try:
        session_mgr = get_session_manager()
        memory = session_mgr.get_session(session_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "bookmarks": [
                {
                    "id": bid,
                    "label": bm.label,
                    "description": bm.description,
                    "timestamp": bm.timestamp,
                    "tags": bm.tags,
                    "importance": bm.importance,
                    "layer": bm.layer.value
                }
                for bid, bm in memory.bookmarks.items()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QuerySessionRequest(BaseModel):
    query: str
    layers: Optional[List[str]] = None
    n_results: int = 5

@app.post("/sessions/{session_id}/query")
async def query_session_memory(session_id: str, request: QuerySessionRequest):
    """Query hierarchical memory in session"""
    try:
        session_mgr = get_session_manager()
        memory = session_mgr.get_session(session_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Session not found")
        
        layers = None
        if request.layers:
            layers = [MemoryLayer(layer) for layer in request.layers]
        
        results = memory.query_memory(
            query=request.query,
            layers=layers,
            n_results=request.n_results
        )
        
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== Medical Data Management (HIPAA - Unified Deletion) =====

@app.get("/medical/summary")
async def get_medical_data_summary():
    """Get summary of ALL medical data (peer + assistant) before deletion"""
    try:
        session_mgr = get_session_manager()
        summary = session_mgr.get_medical_data_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteMedicalDataRequest(BaseModel):
    confirmation: str  # Must be "DELETE_ALL_MEDICAL_DATA"

@app.post("/medical/delete-all")
async def delete_all_medical_data(request: DeleteMedicalDataRequest):
    """
    ⚠️ DANGER: Delete ALL medical data (peer support + medical assistant)
    This includes:
    - All Meta-Hiro peer support conversations
    - All medical assistant conversations
    - All encrypted medical ChromaDB data
    
    Requires confirmation string: "DELETE_ALL_MEDICAL_DATA"
    General chat/story memories are NOT affected.
    """
    try:
        # Require explicit confirmation
        if request.confirmation != "DELETE_ALL_MEDICAL_DATA":
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation. Must be 'DELETE_ALL_MEDICAL_DATA'"
            )
        
        session_mgr = get_session_manager()
        result = session_mgr.delete_all_medical_data()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/medical/sessions")
async def list_medical_sessions():
    """List all medical sessions (peer + assistant)"""
    try:
        session_mgr = get_session_manager()
        all_sessions = session_mgr.list_sessions()
        
        # Filter to only medical sessions
        medical_sessions = [
            s for s in all_sessions 
            if s.get("is_medical", False)
        ]
        
        return {
            "medical_sessions": medical_sessions,
            "count": len(medical_sessions)
        }
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
