import json
import logging
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple

from core.security import SafeSandbox

logger = logging.getLogger("AuraNexus.Storage")

class LocalVectorStore:
    """
    A lightweight, zero-dependency embedded vector database.
    Performs in-memory cosine similarity math and persists indexes
    directly to flat files on disk. Perfect for low-spec consumer machines.
    """
    
    def __init__(
        self,
        storage_path: str | Path = "vector_index.json",
        sandbox: SafeSandbox | None = None,
    ):
        self.sandbox = sandbox or SafeSandbox()
        self.storage_path = self.sandbox.sanitize_path(storage_path)
        # In-memory index structure: list of dicts containing {"vector": [...], "text": "...", "metadata": {...}}
        self._index: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        """Loads an existing vector index from disk if it exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                logger.info(f"Loaded {len(self._index)} vectors from local storage.")
            except Exception as e:
                logger.error(f"Failed to read vector index file: {e}. Starting fresh.")
                self._index = []

    def save_index(self) -> None:
        """Persists the current in-memory vector index cleanly back to disk."""
        try:
            # Ensure target directory exists within the safe sandbox workspace bounds
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
            logger.info("Successfully persisted vector index to disk.")
        except Exception as e:
            logger.error(f"Failed to save vector index to disk: {e}")

    def add_vector(self, vector: List[float], text: str, metadata: Dict[str, Any]) -> None:
        """Inserts a text chunk alongside its vector representation into the database."""
        if not vector:
            raise ValueError("Vector cannot be empty.")

        validated_vector: List[float] = []
        for value in vector:
            if not isinstance(value, (int, float)):
                raise ValueError("Vector contains a non-numeric value.")
            float_value = float(value)
            if not math.isfinite(float_value):
                raise ValueError("Vector contains a non-finite value.")
            validated_vector.append(float_value)

        self._index.append({
            "vector": validated_vector,
            "text": text,
            "metadata": metadata
        })

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates native mathematical cosine similarity between two float vectors."""
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
            
        return dot_product / (norm_a * norm_b)

    def query_similarity(self, query_vector: List[float], top_k: int = 3) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Scans the local index, calculates similarities, and returns the top_k
        closest matching documentation or memory text snippets.
        """
        if not self._index:
            return []

        scored_results: List[Tuple[str, Dict[str, Any], float]] = []
        
        for item in self._index:
            score = self._cosine_similarity(query_vector, item["vector"])
            scored_results.append((item["text"], item["metadata"], score))
            
        # Sort by mathematical score in descending order
        scored_results.sort(key=lambda x: x[2], reverse=True)
        return scored_results[:top_k]