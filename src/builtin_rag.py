"""Built-in RAG (Retrieval Augmented Generation) system for AuraNexus.
Uses ChromaDB for vector storage and sentence-transformers for embeddings.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    chromadb = None
    SentenceTransformer = None


class BuiltInRAG:
    """Built-in RAG system using ChromaDB."""
    
    def __init__(self, data_dir: str = "data/rag"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if not RAG_AVAILABLE:
            raise ImportError("ChromaDB and sentence-transformers required. Install with: pip install chromadb sentence-transformers")
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.data_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="auranexus_memory",
            metadata={"description": "AuraNexus conversation memory"}
        )
        
        # Initialize embedding model (lightweight)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def add_conversation(self, messages: List[Dict[str, str]], metadata: Optional[Dict] = None) -> str:
        """Add a conversation to RAG memory.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            metadata: Optional metadata (timestamp, tags, etc.)
            
        Returns:
            Document ID
        """
        # Create conversation text
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in messages
        ])
        
        # Prepare metadata
        doc_metadata = {
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            "type": "conversation"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        # Generate unique ID
        doc_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Add to collection
        self.collection.add(
            documents=[conversation_text],
            metadatas=[doc_metadata],
            ids=[doc_id]
        )
        
        return doc_id
    
    def add_document(self, content: str, metadata: Optional[Dict] = None) -> str:
        """Add a single document to RAG memory.
        
        Args:
            content: Document text
            metadata: Optional metadata
            
        Returns:
            Document ID
        """
        doc_metadata = {
            "timestamp": datetime.now().isoformat(),
            "type": "document"
        }
        if metadata:
            doc_metadata.update(metadata)
        
        doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        self.collection.add(
            documents=[content],
            metadatas=[doc_metadata],
            ids=[doc_id]
        )
        
        return doc_id
    
    def query(self, query_text: str, n_results: int = 3) -> List[Dict]:
        """Query the RAG memory for relevant context.
        
        Args:
            query_text: Query string
            n_results: Number of results to return
            
        Returns:
            List of result dicts with 'content', 'metadata', and 'distance'
        """
        results = self.collection.query(
            query_texts=[query_text],
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
    
    def get_context(self, query_text: str, n_results: int = 3) -> str:
        """Get formatted context string for RAG augmentation.
        
        Args:
            query_text: Query string
            n_results: Number of results to include
            
        Returns:
            Formatted context string
        """
        results = self.query(query_text, n_results)
        
        if not results:
            return ""
        
        context_parts = ["Relevant context from memory:"]
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n[Memory {i}]:")
            context_parts.append(result['content'][:500])  # Limit to 500 chars
        
        return "\n".join(context_parts)
    
    def clear_memory(self):
        """Clear all memories from the collection."""
        # Delete and recreate collection
        self.client.delete_collection("auranexus_memory")
        self.collection = self.client.get_or_create_collection(
            name="auranexus_memory",
            metadata={"description": "AuraNexus conversation memory"}
        )
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG memory."""
        count = self.collection.count()
        return {
            "total_documents": count,
            "data_directory": str(self.data_dir),
            "collection_name": self.collection.name
        }
