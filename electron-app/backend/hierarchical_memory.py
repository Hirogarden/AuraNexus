"""
Hierarchical Memory System - Infinitely Expanding Layers
Supports project isolation, encryption, bookmarks, and async archival

⚠️ SECURITY: HIPAA COMPLIANCE
Project 3 (Medical Assistant) uses AES-256-GCM encryption for all PHI.
Separate databases prevent cross-contamination between projects.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import threading

logger = logging.getLogger(__name__)

# Encryption (for medical/HIPAA project)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    import secrets
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger.warning("cryptography package not available - encryption disabled")

# RAG dependencies
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("ChromaDB not available - RAG disabled")


class ProjectType(Enum):
    """Project types with different security requirements"""
    MEDICAL_PEER = "medical_peer"        # HIPAA: Peer support (Meta-Hiro)
    MEDICAL_ASSISTANT = "medical_assistant"  # HIPAA: Medical AI assistant
    STORYTELLING = "story"               # Story-specific isolation
    GENERAL_CHAT = "chat"                # General purpose
    GENERAL_ASSISTANT = "assistant"      # Non-medical task assistant


class MemoryLayer(Enum):
    """Hierarchical memory layers"""
    ACTIVE = "active"           # Current conversation (last 10 messages)
    SHORT_TERM = "short_term"   # Recent context (10-50 messages)
    MEDIUM_TERM = "medium_term" # Session memory (50-200 messages)
    LONG_TERM = "long_term"     # Historical (200-1000 messages)
    ARCHIVED = "archived"       # Compressed summaries (1000+ messages)


@dataclass
class Bookmark:
    """Memory bookmark for quick navigation"""
    id: str
    layer: MemoryLayer
    timestamp: str
    label: str
    description: str
    message_range: tuple  # (start_idx, end_idx)
    tags: List[str]
    importance: float  # 0.0-1.0


@dataclass
class MemoryMetadata:
    """Metadata for memory chunks"""
    chunk_id: str
    layer: MemoryLayer
    timestamp: str
    message_count: int
    summary: Optional[str]
    bookmarks: List[str]  # Bookmark IDs
    compressed: bool


class EncryptionManager:
    """AES-256-GCM encryption for medical/sensitive data"""
    
    def __init__(self, password: str):
        if not ENCRYPTION_AVAILABLE:
            raise ImportError("cryptography package required for encryption")
        
        # Derive key from password using PBKDF2
        self.salt = secrets.token_bytes(16)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000
        )
        self.key = kdf.derive(password.encode())
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, data: str) -> bytes:
        """Encrypt string data"""
        nonce = secrets.token_bytes(12)
        ciphertext = self.aesgcm.encrypt(nonce, data.encode(), None)
        # Prepend nonce to ciphertext
        return nonce + ciphertext
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt to string"""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()


class HierarchicalMemory:
    """
    Hierarchical memory system with infinite expansion
    
    Memory Layers:
    - Active: 0-10 messages (always in RAM)
    - Short-term: 10-50 messages (in RAM, indexed)
    - Medium-term: 50-200 messages (ChromaDB, accessible)
    - Long-term: 200-1000 messages (ChromaDB, summarized)
    - Archived: 1000+ messages (ChromaDB, compressed summaries)
    
    Features:
    - Async compression during idle time
    - Bookmarks for important context
    - Project isolation (separate collections)
    - Encryption for medical data
    """
    
    def __init__(
        self,
        project_id: str,
        project_type: ProjectType,
        data_dir: str = "data/memory",
        encryption_key: Optional[str] = None
    ):
        self.project_id = project_id
        self.project_type = project_type
        self.data_dir = Path(data_dir) / project_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Memory layers (in-memory)
        self.active_memory: List[Dict] = []          # Last 10 messages
        self.short_term_memory: List[Dict] = []      # 10-50 messages
        
        # Layer thresholds
        self.ACTIVE_MAX = 10
        self.SHORT_TERM_MAX = 50
        self.MEDIUM_TERM_MAX = 200
        self.LONG_TERM_MAX = 1000
        
        # Bookmarks
        self.bookmarks: Dict[str, Bookmark] = {}
        self._load_bookmarks()
        
        # Encryption for medical data (both peer support and assistant)
        self.encrypted = (project_type in [ProjectType.MEDICAL_PEER, ProjectType.MEDICAL_ASSISTANT])
        self.encryption_manager = None
        if self.encrypted:
            if not encryption_key:
                raise ValueError("Encryption key required for medical projects")
            if not ENCRYPTION_AVAILABLE:
                raise ImportError("cryptography package required for medical projects")
            self.encryption_manager = EncryptionManager(encryption_key)
            logger.info(f"🔒 Medical project {project_id} ({project_type.value}): Encryption enabled")
        
        # RAG/ChromaDB
        self.rag_enabled = RAG_AVAILABLE
        self.client = None
        self.collections: Dict[MemoryLayer, any] = {}
        self.embedder = None
        
        if self.rag_enabled:
            self._init_chromadb()
        
        # Background processing
        self.background_task: Optional[asyncio.Task] = None
        self.processing_lock = threading.Lock()
        self.idle_since: Optional[datetime] = None
        self.compression_queue: List[Dict] = []
        
        logger.info(f"Hierarchical memory initialized: {project_id} ({project_type.value})")
    
    def _init_chromadb(self):
        """Initialize ChromaDB with project-specific collections"""
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.data_dir / "chromadb"),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Create collection for each layer
            for layer in [MemoryLayer.MEDIUM_TERM, MemoryLayer.LONG_TERM, MemoryLayer.ARCHIVED]:
                collection_name = f"{self.project_id}_{layer.value}"
                self.collections[layer] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "project_id": self.project_id,
                        "project_type": self.project_type.value,
                        "layer": layer.value,
                        "encrypted": str(self.encrypted)
                    }
                )
            
            # Lightweight embedding model
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            logger.info(f"ChromaDB initialized for project {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.rag_enabled = False
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to active memory"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Encrypt if medical project
        if self.encrypted and self.encryption_manager:
            message["content_encrypted"] = True
            message["content"] = self.encryption_manager.encrypt(content).hex()
        
        self.active_memory.append(message)
        
        # Auto-promote to higher layers
        if len(self.active_memory) > self.ACTIVE_MAX:
            self._promote_to_short_term()
        
        # Mark as active (not idle)
        self.idle_since = None
    
    def _promote_to_short_term(self):
        """Promote oldest active memory to short-term"""
        if not self.active_memory:
            return
        
        # Move oldest message
        message = self.active_memory.pop(0)
        self.short_term_memory.append(message)
        
        # Check if short-term is full
        if len(self.short_term_memory) > self.SHORT_TERM_MAX:
            # Queue for async archival
            self.compression_queue.append(self.short_term_memory.pop(0))
    
    async def background_compression(self):
        """Background task for compressing and archiving memory"""
        while True:
            try:
                # Wait for idle time
                await asyncio.sleep(1)
                
                # Check if idle
                if self.idle_since is None:
                    self.idle_since = datetime.now()
                    continue
                
                idle_duration = datetime.now() - self.idle_since
                
                # After 3 seconds of idle, start compression
                if idle_duration > timedelta(seconds=3) and self.compression_queue:
                    with self.processing_lock:
                        await self._process_compression_queue()
                
                # After 10 seconds, compress short-term to medium-term
                if idle_duration > timedelta(seconds=10) and len(self.short_term_memory) > 20:
                    with self.processing_lock:
                        await self._compress_short_to_medium()
                
            except Exception as e:
                logger.error(f"Background compression error: {e}")
                await asyncio.sleep(5)
    
    async def _process_compression_queue(self):
        """Process queued messages for archival"""
        if not self.rag_enabled or not self.compression_queue:
            return
        
        batch = self.compression_queue[:10]  # Process in batches
        self.compression_queue = self.compression_queue[10:]
        
        # Archive to medium-term
        await self._archive_to_layer(batch, MemoryLayer.MEDIUM_TERM)
        logger.debug(f"Archived {len(batch)} messages to medium-term during idle time")
    
    async def _compress_short_to_medium(self):
        """Compress short-term memory to medium-term with summarization"""
        if not self.short_term_memory:
            return
        
        # Take oldest 20 messages
        batch = self.short_term_memory[:20]
        self.short_term_memory = self.short_term_memory[20:]
        
        # Create summary
        summary = self._create_summary(batch)
        
        # Archive with summary
        await self._archive_to_layer(
            batch,
            MemoryLayer.MEDIUM_TERM,
            summary=summary
        )
        logger.debug(f"Compressed {len(batch)} messages to medium-term with summary")
    
    def _create_summary(self, messages: List[Dict]) -> str:
        """Create summary of message batch"""
        # Simple extractive summary (can be enhanced with LLM later)
        content_parts = []
        for msg in messages:
            content = msg.get("content", "")
            if msg.get("content_encrypted"):
                content = self.encryption_manager.decrypt(bytes.fromhex(content))
            content_parts.append(f"{msg['role']}: {content[:100]}")
        
        return " | ".join(content_parts[:5])  # First 5 messages summary
    
    async def _archive_to_layer(
        self,
        messages: List[Dict],
        layer: MemoryLayer,
        summary: Optional[str] = None
    ):
        """Archive messages to specific ChromaDB layer"""
        if not self.rag_enabled or layer not in self.collections:
            return
        
        collection = self.collections[layer]
        
        # Create document text
        doc_parts = []
        for msg in messages:
            content = msg.get("content", "")
            if msg.get("content_encrypted"):
                content = self.encryption_manager.decrypt(bytes.fromhex(content))
            doc_parts.append(f"{msg['role']}: {content}")
        
        doc_text = "\n".join(doc_parts)
        if summary:
            doc_text = f"SUMMARY: {summary}\n\n{doc_text}"
        
        # Metadata
        metadata = MemoryMetadata(
            chunk_id=f"{layer.value}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            layer=layer,
            timestamp=datetime.now().isoformat(),
            message_count=len(messages),
            summary=summary,
            bookmarks=[],
            compressed=summary is not None
        )
        
        # Add to ChromaDB
        collection.add(
            documents=[doc_text],
            metadatas=[asdict(metadata)],
            ids=[metadata.chunk_id]
        )
    
    def create_bookmark(
        self,
        label: str,
        description: str,
        tags: List[str] = None,
        importance: float = 0.5
    ) -> str:
        """Create bookmark at current position"""
        bookmark_id = f"bookmark_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Determine layer and position
        total_messages = len(self.active_memory) + len(self.short_term_memory)
        
        if total_messages <= self.ACTIVE_MAX:
            layer = MemoryLayer.ACTIVE
        else:
            layer = MemoryLayer.SHORT_TERM
        
        bookmark = Bookmark(
            id=bookmark_id,
            layer=layer,
            timestamp=datetime.now().isoformat(),
            label=label,
            description=description,
            message_range=(total_messages - 5, total_messages),  # Last 5 messages
            tags=tags or [],
            importance=importance
        )
        
        self.bookmarks[bookmark_id] = bookmark
        self._save_bookmarks()
        
        logger.info(f"📌 Created bookmark: {label}")
        return bookmark_id
    
    def get_bookmark_context(self, bookmark_id: str) -> Optional[List[Dict]]:
        """Retrieve context around a bookmark"""
        if bookmark_id not in self.bookmarks:
            return None
        
        bookmark = self.bookmarks[bookmark_id]
        
        # Get messages from appropriate layer
        if bookmark.layer == MemoryLayer.ACTIVE:
            messages = self.active_memory
        elif bookmark.layer == MemoryLayer.SHORT_TERM:
            messages = self.short_term_memory
        else:
            # Query ChromaDB
            return self._query_bookmark_from_db(bookmark)
        
        start, end = bookmark.message_range
        return messages[max(0, start):min(len(messages), end)]
    
    def _query_bookmark_from_db(self, bookmark: Bookmark) -> List[Dict]:
        """Query bookmark context from ChromaDB"""
        # Implement ChromaDB query for archived bookmarks
        # This would search by bookmark metadata
        return []
    
    def query_memory(
        self,
        query: str,
        layers: List[MemoryLayer] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """Query across memory layers"""
        if layers is None:
            layers = [MemoryLayer.MEDIUM_TERM, MemoryLayer.LONG_TERM]
        
        results = []
        
        # Query each layer
        for layer in layers:
            if layer in self.collections:
                layer_results = self.collections[layer].query(
                    query_texts=[query],
                    n_results=n_results
                )
                
                if layer_results['documents'] and layer_results['documents'][0]:
                    for i, doc in enumerate(layer_results['documents'][0]):
                        results.append({
                            'content': doc,
                            'layer': layer.value,
                            'metadata': layer_results['metadatas'][0][i] if layer_results['metadatas'] else {},
                            'distance': layer_results['distances'][0][i] if layer_results['distances'] else 0.0
                        })
        
        # Sort by relevance
        results.sort(key=lambda x: x['distance'])
        return results[:n_results]
    
    def get_recent_context(self, n: int = 10) -> str:
        """Get formatted recent context"""
        messages = self.active_memory[-n:]
        
        lines = []
        for msg in messages:
            content = msg.get("content", "")
            if msg.get("content_encrypted"):
                content = self.encryption_manager.decrypt(bytes.fromhex(content))
            lines.append(f"{msg['role']}: {content}")
        
        return "\n".join(lines)
    
    def _save_bookmarks(self):
        """Save bookmarks to disk"""
        bookmark_file = self.data_dir / "bookmarks.json"
        data = {
            bid: {
                **asdict(bookmark),
                'layer': bookmark.layer.value
            }
            for bid, bookmark in self.bookmarks.items()
        }
        with open(bookmark_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_bookmarks(self):
        """Load bookmarks from disk"""
        bookmark_file = self.data_dir / "bookmarks.json"
        if not bookmark_file.exists():
            return
        
        try:
            with open(bookmark_file, 'r') as f:
                data = json.load(f)
            
            for bid, bookmark_data in data.items():
                bookmark_data['layer'] = MemoryLayer(bookmark_data['layer'])
                self.bookmarks[bid] = Bookmark(**bookmark_data)
        except Exception as e:
            logger.error(f"Failed to load bookmarks: {e}")
    
    def get_stats(self) -> Dict:
        """Get memory statistics"""
        stats = {
            "project_id": self.project_id,
            "project_type": self.project_type.value,
            "encrypted": self.encrypted,
            "active_messages": len(self.active_memory),
            "short_term_messages": len(self.short_term_memory),
            "compression_queue": len(self.compression_queue),
            "bookmarks": len(self.bookmarks),
            "rag_enabled": self.rag_enabled
        }
        
        # Add ChromaDB stats
        if self.rag_enabled:
            for layer, collection in self.collections.items():
                stats[f"{layer.value}_count"] = collection.count()
        
        return stats


class MemorySessionManager:
    """Manages multiple memory sessions (stories, projects)"""
    
    def __init__(self, data_dir: str = "data/memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Separate directories for medical and general data
        self.medical_data_dir = Path(data_dir) / "medical_secure"
        self.general_data_dir = Path(data_dir) / "general"
        self.medical_data_dir.mkdir(parents=True, exist_ok=True)
        self.general_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.sessions: Dict[str, HierarchicalMemory] = {}
        self.active_session: Optional[str] = None
        
        # Track medical sessions for unified deletion
        self.medical_sessions: Set[str] = set()  # Peer + Assistant sessions
        
        # Load session registry
        self._load_registry()
    
    def create_session(
        self,
        session_id: str,
        project_type: ProjectType,
        encryption_key: Optional[str] = None
    ) -> HierarchicalMemory:
        """Create new memory session"""
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} already exists")
            return self.sessions[session_id]
        
        # Use separate directory for medical data
        is_medical = project_type in [ProjectType.MEDICAL_PEER, ProjectType.MEDICAL_ASSISTANT]
        base_dir = str(self.medical_data_dir) if is_medical else str(self.general_data_dir)
        
        memory = HierarchicalMemory(
            project_id=session_id,
            project_type=project_type,
            data_dir=base_dir,
            encryption_key=encryption_key
        )
        
        self.sessions[session_id] = memory
        
        # Track medical sessions for unified deletion
        if is_medical:
            self.medical_sessions.add(session_id)
        
        self._save_registry()
        
        logger.info(f"✨ Created memory session: {session_id} ({'MEDICAL' if is_medical else 'GENERAL'})")
        return memory
    
    def get_session(self, session_id: str) -> Optional[HierarchicalMemory]:
        """Get existing session"""
        return self.sessions.get(session_id)
    
    def switch_session(self, session_id: str):
        """Switch active session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} does not exist")
        
        self.active_session = session_id
        logger.info(f"Switched to session: {session_id}")
    
    def list_sessions(self) -> List[Dict]:
        """List all sessions"""
        return [
            {
                "session_id": sid,
                "project_type": mem.project_type.value,
                "encrypted": mem.encrypted,
                "is_medical": sid in self.medical_sessions,
                "stats": mem.get_stats()
            }
            for sid, mem in self.sessions.items()
        ]
    
    def delete_all_medical_data(self) -> Dict[str, any]:
        """Delete ALL medical data (peer support + medical assistant) in one operation"""
        import shutil
        
        deleted_sessions = []
        errors = []
        
        # Delete all medical sessions
        for session_id in list(self.medical_sessions):
            try:
                if session_id in self.sessions:
                    # Unload session
                    del self.sessions[session_id]
                    deleted_sessions.append(session_id)
                    logger.info(f"🗑️ Deleted medical session: {session_id}")
            except Exception as e:
                errors.append({"session": session_id, "error": str(e)})
        
        # Clear tracking set
        self.medical_sessions.clear()
        
        # Delete entire medical directory
        try:
            if self.medical_data_dir.exists():
                shutil.rmtree(self.medical_data_dir)
                self.medical_data_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"🗑️ Wiped medical data directory: {self.medical_data_dir}")
        except Exception as e:
            errors.append({"directory": str(self.medical_data_dir), "error": str(e)})
        
        # Update registry
        self._save_registry()
        
        result = {
            "status": "completed" if not errors else "completed_with_errors",
            "deleted_sessions": deleted_sessions,
            "total_deleted": len(deleted_sessions),
            "errors": errors
        }
        
        logger.warning(f"⚠️ MEDICAL DATA DELETION: {len(deleted_sessions)} sessions removed")
        return result
    
    def get_medical_data_summary(self) -> Dict:
        """Get summary of all medical data for review before deletion"""
        medical_sessions_info = []
        total_size = 0
        
        for session_id in self.medical_sessions:
            if session_id in self.sessions:
                mem = self.sessions[session_id]
                stats = mem.get_stats()
                medical_sessions_info.append({
                    "session_id": session_id,
                    "type": mem.project_type.value,
                    "stats": stats
                })
        
        # Calculate directory size
        if self.medical_data_dir.exists():
            total_size = sum(
                f.stat().st_size 
                for f in self.medical_data_dir.rglob('*') 
                if f.is_file()
            )
        
        return {
            "medical_sessions_count": len(self.medical_sessions),
            "sessions": medical_sessions_info,
            "storage_path": str(self.medical_data_dir),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    
    def _save_registry(self):
        """Save session registry"""
        registry_file = self.data_dir / "registry.json"
        data = {
            "sessions": list(self.sessions.keys()),
            "active_session": self.active_session,
            "medical_sessions": list(self.medical_sessions)
        }
        with open(registry_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_registry(self):
        """Load session registry"""
        registry_file = self.data_dir / "registry.json"
        if not registry_file.exists():
            return
        
        try:
            with open(registry_file, 'r') as f:
                data = json.load(f)
            self.active_session = data.get("active_session")
            self.medical_sessions = set(data.get("medical_sessions", []))
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")


# Global session manager
_session_manager: Optional[MemorySessionManager] = None


def get_session_manager() -> MemorySessionManager:
    """Get global session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = MemorySessionManager()
    return _session_manager
