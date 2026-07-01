import json
import logging
import math
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

from core.security import SafeSandbox

logger = logging.getLogger("AuraNexus.Storage")


class LocalVectorStore:
    """
    A lightweight, zero-dependency hierarchical RAG store.

    HiRAG layout:
    - Local Layer: granular text nodes and embeddings.
    - Global Layer: recursively produced cluster centroids.
    - Bridge Map: explicit mapping from local node IDs to parent cluster IDs.
    """

    def __init__(
        self,
        storage_path: str | Path = "vector_index.json",
        sandbox: SafeSandbox | None = None,
        max_cluster_size: int = 24,
        max_cluster_depth: int = 6,
    ):
        self.sandbox = sandbox or SafeSandbox()
        self.storage_path = self.sandbox.sanitize_path(storage_path)
        if max_cluster_size < 2:
            raise ValueError("max_cluster_size must be at least 2.")
        if max_cluster_depth < 1:
            raise ValueError("max_cluster_depth must be at least 1.")

        self.max_cluster_size = int(max_cluster_size)
        self.max_cluster_depth = int(max_cluster_depth)

        self.schema_version = 2
        self.vector_dim: int | None = None
        self._local_nodes: List[Dict[str, Any]] = []
        self._global_clusters: List[Dict[str, Any]] = []
        self._bridge_map: Dict[str, List[int]] = {}
        self._local_to_cluster: Dict[int, str] = {}
        self._next_local_id = 1
        self._next_cluster_id = 1

        # Backward compatibility surface used by older tests/callers.
        self._index: List[Dict[str, Any]] = []

        self._load_index()

    def _empty_payload(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "vector_dim": self.vector_dim,
            "max_cluster_size": self.max_cluster_size,
            "max_cluster_depth": self.max_cluster_depth,
            "next_local_id": self._next_local_id,
            "next_cluster_id": self._next_cluster_id,
            "local_nodes": self._local_nodes,
            "global_clusters": self._global_clusters,
            "bridge_map": self._bridge_map,
        }

    def _load_index(self) -> None:
        """Loads an existing HiRAG index (or migrates legacy flat format)."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                if isinstance(raw, list):
                    # Legacy v1: flat list of vectors.
                    self._load_from_legacy_flat_index(raw)
                    logger.info(
                        "Loaded legacy vector index and migrated to HiRAG with %d local nodes.",
                        len(self._local_nodes),
                    )
                elif isinstance(raw, dict):
                    self._load_from_hirag_payload(raw)
                    logger.info(
                        "Loaded HiRAG index with %d local nodes and %d global clusters.",
                        len(self._local_nodes),
                        len(self._global_clusters),
                    )
                else:
                    raise ValueError("Unsupported index format.")
            except Exception as e:
                logger.error("Failed to read vector index file: %s. Starting fresh.", e)
                self._reset()

        self._sync_legacy_index_view()

    def _reset(self) -> None:
        self.vector_dim = None
        self._local_nodes = []
        self._global_clusters = []
        self._bridge_map = {}
        self._local_to_cluster = {}
        self._next_local_id = 1
        self._next_cluster_id = 1
        self._index = []

    def _load_from_legacy_flat_index(self, raw_index: List[Dict[str, Any]]) -> None:
        self._reset()
        for item in raw_index:
            vector = item.get("vector", [])
            text = str(item.get("text", ""))
            metadata = item.get("metadata", {})
            self.add_vector(vector=vector, text=text, metadata=metadata)

    def _load_from_hirag_payload(self, payload: Dict[str, Any]) -> None:
        self._reset()
        self.vector_dim = payload.get("vector_dim")
        self.max_cluster_size = int(payload.get("max_cluster_size", self.max_cluster_size))
        self.max_cluster_depth = int(payload.get("max_cluster_depth", self.max_cluster_depth))

        local_nodes = payload.get("local_nodes", [])
        global_clusters = payload.get("global_clusters", [])
        bridge_map = payload.get("bridge_map", {})
        next_local_id = int(payload.get("next_local_id", 1))
        next_cluster_id = int(payload.get("next_cluster_id", 1))

        if not isinstance(local_nodes, list) or not isinstance(global_clusters, list) or not isinstance(bridge_map, dict):
            raise ValueError("Corrupt HiRAG payload.")

        validated_nodes: List[Dict[str, Any]] = []
        observed_ids: set[int] = set()
        for node in local_nodes:
            if not isinstance(node, dict):
                continue
            node_id = int(node.get("id", 0))
            if node_id <= 0 or node_id in observed_ids:
                continue
            vector = self._validate_vector(node.get("vector", []), enforce_dim=False)
            if self.vector_dim is None:
                self.vector_dim = len(vector)
            if len(vector) != self.vector_dim:
                continue
            validated_nodes.append(
                {
                    "id": node_id,
                    "text": str(node.get("text", "")),
                    "vector": vector,
                    "metadata": node.get("metadata", {}) if isinstance(node.get("metadata", {}), dict) else {},
                    "created_at": float(node.get("created_at", time.time())),
                }
            )
            observed_ids.add(node_id)

        self._local_nodes = sorted(validated_nodes, key=lambda node: node["id"])
        self._next_local_id = max([node["id"] for node in self._local_nodes], default=0) + 1
        self._next_local_id = max(self._next_local_id, next_local_id)

        self._global_clusters = []
        self._bridge_map = {}
        self._local_to_cluster = {}

        cluster_ids: set[str] = set()
        for cluster in global_clusters:
            if not isinstance(cluster, dict):
                continue
            cluster_id = str(cluster.get("id", "")).strip()
            centroid = cluster.get("centroid", [])
            if not cluster_id or cluster_id in cluster_ids:
                continue
            try:
                centroid_vector = self._validate_vector(centroid, enforce_dim=True)
            except ValueError:
                continue
            self._global_clusters.append(
                {
                    "id": cluster_id,
                    "centroid": centroid_vector,
                    "size": int(cluster.get("size", 0)),
                    "updated_at": float(cluster.get("updated_at", time.time())),
                }
            )
            cluster_ids.add(cluster_id)

        for key, values in bridge_map.items():
            cluster_id = str(key).strip()
            if cluster_id not in cluster_ids or not isinstance(values, list):
                continue
            valid_local_ids = []
            for value in values:
                try:
                    local_id = int(value)
                except Exception:
                    continue
                if local_id in observed_ids:
                    valid_local_ids.append(local_id)
                    self._local_to_cluster[local_id] = cluster_id
            if valid_local_ids:
                self._bridge_map[cluster_id] = sorted(set(valid_local_ids))

        self._next_cluster_id = max(self._extract_numeric_cluster_id(cluster_id) for cluster_id in cluster_ids) + 1
        self._next_cluster_id = max(self._next_cluster_id, next_cluster_id)

        # If loaded graph is partial/corrupt, rebuild from local nodes.
        if not self._local_nodes:
            self._global_clusters = []
            self._bridge_map = {}
            self._local_to_cluster = {}
        elif not self._global_clusters or len(self._local_to_cluster) != len(self._local_nodes):
            self._rebuild_hierarchy()

    def _extract_numeric_cluster_id(self, cluster_id: str) -> int:
        if not cluster_id.startswith("cluster_"):
            return 0
        suffix = cluster_id.split("cluster_", 1)[1]
        if suffix.isdigit():
            return int(suffix)
        return 0

    def _sync_legacy_index_view(self) -> None:
        self._index = [
            {
                "vector": list(node["vector"]),
                "text": node["text"],
                "metadata": dict(node["metadata"]),
            }
            for node in self._local_nodes
        ]

    def save_index(self) -> None:
        """Persists the full HiRAG structure to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = self._empty_payload()
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info("Successfully persisted vector index to disk.")
        except Exception as e:
            logger.error("Failed to save vector index to disk: %s", e)

    def _validate_vector(self, vector: List[float], enforce_dim: bool) -> List[float]:
        if not isinstance(vector, list) or not vector:
            raise ValueError("Vector cannot be empty.")

        validated_vector: List[float] = []
        for value in vector:
            if not isinstance(value, (int, float)):
                raise ValueError("Vector contains a non-numeric value.")
            float_value = float(value)
            if not math.isfinite(float_value):
                raise ValueError("Vector contains a non-finite value.")
            validated_vector.append(float_value)

        if self.vector_dim is None:
            self.vector_dim = len(validated_vector)

        if enforce_dim and len(validated_vector) != self.vector_dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.vector_dim}, got {len(validated_vector)}."
            )

        return validated_vector

    def add_vector(self, vector: List[float], text: str, metadata: Dict[str, Any]) -> None:
        """Adds a local node and rebuilds global clusters + bridge mapping."""
        validated_vector = self._validate_vector(vector, enforce_dim=True)
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary.")

        node = {
            "id": self._next_local_id,
            "text": str(text),
            "vector": validated_vector,
            "metadata": dict(metadata),
            "created_at": time.time(),
        }
        self._next_local_id += 1
        self._local_nodes.append(node)
        self._rebuild_hierarchy()
        self._sync_legacy_index_view()

    def _node_by_id(self, local_id: int) -> Dict[str, Any] | None:
        for node in self._local_nodes:
            if node["id"] == local_id:
                return node
        return None

    @staticmethod
    def _centroid(vectors: List[List[float]]) -> List[float]:
        if not vectors:
            return []
        dim = len(vectors[0])
        sums = [0.0] * dim
        for vector in vectors:
            for index, value in enumerate(vector):
                sums[index] += value
        count = float(len(vectors))
        return [value / count for value in sums]

    def _distance(self, vec_a: List[float], vec_b: List[float]) -> float:
        # Smaller is closer; based on cosine, range [0, 2].
        return 1.0 - self._cosine_similarity(vec_a, vec_b)

    def _choose_split_anchors(self, node_ids: List[int]) -> Tuple[int, int]:
        if len(node_ids) < 2:
            only = node_ids[0]
            return only, only

        first = node_ids[0]
        first_vector = self._node_by_id(first)["vector"]

        farthest = first
        farthest_distance = -1.0
        for node_id in node_ids:
            node_vector = self._node_by_id(node_id)["vector"]
            distance = self._distance(first_vector, node_vector)
            if distance > farthest_distance:
                farthest_distance = distance
                farthest = node_id

        second_anchor_vector = self._node_by_id(farthest)["vector"]
        opposite = farthest
        opposite_distance = -1.0
        for node_id in node_ids:
            node_vector = self._node_by_id(node_id)["vector"]
            distance = self._distance(second_anchor_vector, node_vector)
            if distance > opposite_distance:
                opposite_distance = distance
                opposite = node_id

        if farthest == opposite:
            return node_ids[0], node_ids[-1]
        return farthest, opposite

    def _split_node_ids(self, node_ids: List[int]) -> Tuple[List[int], List[int]]:
        left_anchor_id, right_anchor_id = self._choose_split_anchors(node_ids)
        left_anchor_vector = self._node_by_id(left_anchor_id)["vector"]
        right_anchor_vector = self._node_by_id(right_anchor_id)["vector"]

        left_ids: List[int] = []
        right_ids: List[int] = []

        for node_id in node_ids:
            node_vector = self._node_by_id(node_id)["vector"]
            left_distance = self._distance(node_vector, left_anchor_vector)
            right_distance = self._distance(node_vector, right_anchor_vector)
            if left_distance <= right_distance:
                left_ids.append(node_id)
            else:
                right_ids.append(node_id)

        if not left_ids or not right_ids:
            midpoint = max(1, len(node_ids) // 2)
            left_ids = node_ids[:midpoint]
            right_ids = node_ids[midpoint:]

        return left_ids, right_ids

    def _new_cluster_id(self) -> str:
        cluster_id = f"cluster_{self._next_cluster_id}"
        self._next_cluster_id += 1
        return cluster_id

    def _register_cluster(self, node_ids: List[int]) -> str:
        vectors = [self._node_by_id(node_id)["vector"] for node_id in node_ids]
        centroid = self._centroid(vectors)
        cluster_id = self._new_cluster_id()

        cluster = {
            "id": cluster_id,
            "centroid": centroid,
            "size": len(node_ids),
            "updated_at": time.time(),
        }
        self._global_clusters.append(cluster)

        self._bridge_map[cluster_id] = sorted(node_ids)
        for node_id in node_ids:
            self._local_to_cluster[node_id] = cluster_id
        return cluster_id

    def _build_recursive_clusters(self, node_ids: List[int], depth: int) -> None:
        if not node_ids:
            return

        if len(node_ids) <= self.max_cluster_size or depth >= self.max_cluster_depth:
            self._register_cluster(node_ids)
            return

        left_ids, right_ids = self._split_node_ids(node_ids)
        self._build_recursive_clusters(left_ids, depth + 1)
        self._build_recursive_clusters(right_ids, depth + 1)

    def _rebuild_hierarchy(self) -> None:
        self._global_clusters = []
        self._bridge_map = {}
        self._local_to_cluster = {}

        if not self._local_nodes:
            return

        self._next_cluster_id = 1
        ordered_ids = [node["id"] for node in self._local_nodes]
        self._build_recursive_clusters(ordered_ids, depth=0)

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

    def query_hierarchical(
        self,
        query_vector: List[float],
        top_k: int = 3,
        top_clusters: int = 2,
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Multi-hop HiRAG retrieval.

        Step 1: score query against global cluster centroids.
        Step 2: use bridge map to hop into matching local nodes.
        Step 3: rank those local nodes by cosine similarity.
        """
        if not self._local_nodes:
            return []

        validated_query = self._validate_vector(query_vector, enforce_dim=True)
        cluster_scores: List[Tuple[str, float]] = []

        for cluster in self._global_clusters:
            score = self._cosine_similarity(validated_query, cluster["centroid"])
            cluster_scores.append((cluster["id"], score))

        cluster_scores.sort(key=lambda item: item[1], reverse=True)

        if top_clusters < 1:
            top_clusters = 1

        selected_clusters = [cluster_id for cluster_id, _ in cluster_scores[:top_clusters]]
        candidate_ids: List[int] = []
        for cluster_id in selected_clusters:
            candidate_ids.extend(self._bridge_map.get(cluster_id, []))

        candidate_ids = sorted(set(candidate_ids))
        if not candidate_ids:
            candidate_ids = [node["id"] for node in self._local_nodes]

        scored_results: List[Tuple[str, Dict[str, Any], float]] = []
        for local_id in candidate_ids:
            node = self._node_by_id(local_id)
            if node is None:
                continue
            similarity = self._cosine_similarity(validated_query, node["vector"])
            metadata = dict(node["metadata"])
            metadata["hirag_local_id"] = local_id
            metadata["hirag_cluster_id"] = self._local_to_cluster.get(local_id)
            scored_results.append((node["text"], metadata, similarity))

        scored_results.sort(key=lambda item: item[2], reverse=True)
        return scored_results[:top_k]

    def query_similarity(self, query_vector: List[float], top_k: int = 3) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Backward-compatible entrypoint that now routes to hierarchical retrieval.
        """
        cluster_count = len(self._global_clusters)
        top_clusters = min(max(cluster_count, 1), 3)
        return self.query_hierarchical(query_vector=query_vector, top_k=top_k, top_clusters=top_clusters)

    def get_hirag_state(self) -> Dict[str, Any]:
        """Returns a read-friendly snapshot of the current HiRAG layers."""
        return {
            "schema_version": self.schema_version,
            "vector_dim": self.vector_dim,
            "local_count": len(self._local_nodes),
            "global_count": len(self._global_clusters),
            "bridge_count": sum(len(ids) for ids in self._bridge_map.values()),
            "clusters": [
                {
                    "id": cluster["id"],
                    "size": cluster["size"],
                    "centroid": list(cluster["centroid"]),
                }
                for cluster in self._global_clusters
            ],
            "bridge_map": {cluster_id: list(local_ids) for cluster_id, local_ids in self._bridge_map.items()},
        }