"""
Memory Manager for AuraNexus agents
Handles conversation history and semantic memory (RAG)

⚠️ SECURITY: PHI HANDLING
Memory system stores Protected Health Information (PHI) from conversations.

REQUIREMENTS:
- Encrypt stored conversations (Phase 2)
- Audit all memory access (Phase 2)
- Support data deletion (Right to be Forgotten)
- Never log actual message content

See SECURITY_CHECKLIST.md before modifying.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import RAG (optional dependency)
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("ChromaDB/sentence-transformers not available. Install with: pip install chromadb sentence-transformers")


class MemoryManager:
    """
    Unified memory system combining:
    1. Short-term: Recent conversation history (in-memory)
    2. Long-term: Semantic memory via RAG (ChromaDB)
    """
    
    def __init__(self, data_dir: str = "data/memory", enable_rag: bool = True):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Short-term memory (recent messages)
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 20
        
        # Batch archival for better I/O performance
        self.archive_batch_size = 10  # Archive in batches of 10
        self.pending_archive: List[Dict] = []
        
        # Long-term semantic memory (RAG)
        self.rag_enabled = enable_rag and RAG_AVAILABLE
        self.rag_collection = None
        self.embedder = None
        
        if self.rag_enabled:
            self._init_rag()
        else:
            logger.info("RAG memory disabled or unavailable")
    
    def _init_rag(self):
        """Initialize ChromaDB for semantic memory"""
        try:
            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(
                path=str(self.data_dir / "rag"),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.rag_collection = self.client.get_or_create_collection(
                name="auranexus_memory",
                metadata={"description": "AuraNexus conversation memory"}
            )
            
            # Initialize lightweight embedding model
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            logger.info("RAG memory initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            self.rag_enabled = False
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add message to short-term memory
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (agent name, timestamp, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if metadata:
            message.update(metadata)
        
        self.conversation_history.append(message)
        
        # Trim old messages with batch archival
        if len(self.conversation_history) > self.max_history:
            # Move old messages to pending archive
            if self.rag_enabled:
                old_messages = self.conversation_history[:-self.max_history]
                self.pending_archive.extend(old_messages)
                
                # Archive in batches to reduce I/O overhead
                if len(self.pending_archive) >= self.archive_batch_size:
                    self._archive_to_rag(self.pending_archive)
                    self.pending_archive = []
            
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        logger.debug(f"Added message to short-term memory (role={role})")
    
    def get_recent_history(self, n: int = 10) -> List[Dict[str, str]]:
        """Get N most recent messages from short-term memory"""
        return self.conversation_history[-n:]
    
    def get_formatted_history(self, n: int = 10) -> str:
        """Get formatted conversation history for prompt context"""
        recent = self.get_recent_history(n)
        
        if not recent:
            return ""
        
        lines = ["Recent conversation:"]
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
    
    def query_long_term_memory(self, query: str, n_results: int = 3) -> List[Dict]:
        """
        Query semantic memory (RAG) for relevant past context
        
        Args:
            query: Query text
            n_results: Number of results to retrieve
            
        Returns:
            List of relevant memory entries
        """
        if not self.rag_enabled or not self.rag_collection:
            return []
        
        try:
            results = self.rag_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Long-term memory query failed: {e}")
            return []
    
    def get_augmented_context(self, query: str, n_results: int = 3, max_chars: int = 500) -> str:
        """
        Get formatted context from long-term memory for RAG augmentation
        
        Args:
            query: Query to find relevant memories
            n_results: Number of memory entries to retrieve
            max_chars: Maximum characters per memory entry
            
        Returns:
            Formatted context string to add to prompts
        """
        results = self.query_long_term_memory(query, n_results)
        
        if not results:
            return ""
        
        context_parts = ["Relevant context from past conversations:"]
        for i, result in enumerate(results, 1):
            content = result['content'][:max_chars]
            context_parts.append(f"\n[Memory {i}]:")
            context_parts.append(content)
        
        return "\n".join(context_parts)
    
    def _archive_to_rag(self, messages: List[Dict]):
        """Archive messages to long-term RAG memory"""
        if not self.rag_enabled or not self.rag_collection:
            return
        
        try:
            # Create conversation text
            conversation_text = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
                for msg in messages
            ])
            
            # Metadata
            doc_metadata = {
                "timestamp": datetime.now().isoformat(),
                "message_count": len(messages),
                "type": "archived_conversation"
            }
            
            # Generate unique ID
            doc_id = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Add to RAG
            self.rag_collection.add(
                documents=[conversation_text],
                metadatas=[doc_metadata],
                ids=[doc_id]
            )
            
            logger.debug(f"Archived {len(messages)} messages to long-term memory")
            
        except Exception as e:
            logger.error(f"Failed to archive to RAG: {e}")
    
    def save_conversation(self, filepath: str):
        """
        Save conversation history to JSON file
        
        Args:
            filepath: Path to save file
        """
        try:
            save_path = Path(filepath)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "conversation_history": self.conversation_history,
                    "saved_at": datetime.now().isoformat()
                }, f, indent=2)
            
            logger.info(f"Conversation saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
    
    def load_conversation(self, filepath: str):
        """
        Load conversation history from JSON file
        
        Args:
            filepath: Path to load file
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.conversation_history = data.get("conversation_history", [])
            
            logger.info(f"Conversation loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
    
    def clear_short_term(self):
        """Clear short-term memory (conversation history)"""
        self.conversation_history = []
        logger.info("Short-term memory cleared")
    
    def clear_long_term(self):
        """Clear long-term RAG memory"""
        if not self.rag_enabled or not self.client:
            return
        
        try:
            self.client.delete_collection("auranexus_memory")
            self.rag_collection = self.client.get_or_create_collection(
                name="auranexus_memory",
                metadata={"description": "AuraNexus conversation memory"}
            )
            logger.info("Long-term memory cleared")
        except Exception as e:
            logger.error(f"Failed to clear long-term memory: {e}")
    
    def get_stats(self) -> Dict:
        """Get memory statistics"""
        stats = {
            "short_term_messages": len(self.conversation_history),
            "max_history": self.max_history,
            "rag_enabled": self.rag_enabled
        }
        
        if self.rag_enabled and self.rag_collection:
            stats["long_term_documents"] = self.rag_collection.count()
        
        return stats


# Global memory manager instance (singleton)
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(data_dir: str = "data/memory", enable_rag: bool = True) -> MemoryManager:
    """Get or create global memory manager instance"""
    global _memory_manager
    
    if _memory_manager is None:
        _memory_manager = MemoryManager(data_dir=data_dir, enable_rag=enable_rag)
    
    return _memory_manager
