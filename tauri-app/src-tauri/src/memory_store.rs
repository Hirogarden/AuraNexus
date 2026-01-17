// Memory Store Module - Translated from mem0 Python library
// Original: https://github.com/mem0ai/mem0
// License: Apache 2.0

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::SystemTime;
use uuid::Uuid;

/// Memory item stored in the database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryItem {
    pub id: String,
    pub content: String,
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
    pub metadata: HashMap<String, serde_json::Value>,
    pub created_at: SystemTime,
    pub updated_at: SystemTime,
}

/// Filter criteria for querying memories
#[derive(Debug, Default, Clone)]
pub struct MemoryFilters {
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Memory store for managing conversation memories
/// 
/// Translated from mem0's Python implementation to pure Rust.
/// Provides session-scoped memory storage with flexible filtering.
pub struct MemoryStore {
    memories: HashMap<String, MemoryItem>,
}

impl MemoryStore {
    /// Create a new memory store
    pub fn new() -> Self {
        Self {
            memories: HashMap::new(),
        }
    }

    /// Add a new memory with session identifiers
    /// 
    /// # Arguments
    /// * `content` - The memory content to store
    /// * `user_id` - Optional user identifier for session scoping
    /// * `agent_id` - Optional agent identifier for session scoping
    /// * `run_id` - Optional run identifier for session scoping
    /// * `metadata` - Additional metadata to attach to the memory
    /// 
    /// # Returns
    /// The ID of the created memory
    /// 
    /// # Example
    /// ```rust
    /// let store = MemoryStore::new();
    /// let id = store.add(
    ///     "Patient has diabetes type 2",
    ///     Some("patient_123"),
    ///     None,
    ///     None,
    ///     HashMap::new()
    /// );
    /// ```
    pub fn add(
        &mut self,
        content: impl Into<String>,
        user_id: Option<String>,
        agent_id: Option<String>,
        run_id: Option<String>,
        mut metadata: HashMap<String, serde_json::Value>,
    ) -> String {
        let id = Uuid::new_v4().to_string();
        let now = SystemTime::now();

        // Add session identifiers to metadata
        if let Some(uid) = &user_id {
            metadata.insert("user_id".to_string(), serde_json::json!(uid));
        }
        if let Some(aid) = &agent_id {
            metadata.insert("agent_id".to_string(), serde_json::json!(aid));
        }
        if let Some(rid) = &run_id {
            metadata.insert("run_id".to_string(), serde_json::json!(rid));
        }

        let memory = MemoryItem {
            id: id.clone(),
            content: content.into(),
            user_id,
            agent_id,
            run_id,
            metadata,
            created_at: now,
            updated_at: now,
        };

        self.memories.insert(id.clone(), memory);
        id
    }

    /// Retrieve a specific memory by ID
    /// 
    /// # Arguments
    /// * `memory_id` - The ID of the memory to retrieve
    /// 
    /// # Returns
    /// The memory if found, None otherwise
    pub fn get(&self, memory_id: &str) -> Option<&MemoryItem> {
        self.memories.get(memory_id)
    }

    /// Get all memories matching the given filters
    /// 
    /// # Arguments
    /// * `filters` - Filter criteria for session scoping
    /// * `limit` - Maximum number of memories to return
    /// 
    /// # Returns
    /// Vector of memories matching the filters, sorted by creation time (newest first)
    pub fn get_all(&self, filters: &MemoryFilters, limit: usize) -> Vec<&MemoryItem> {
        let mut results: Vec<&MemoryItem> = self
            .memories
            .values()
            .filter(|memory| self.matches_filters(memory, filters))
            .collect();

        // Sort by created_at descending (newest first)
        results.sort_by(|a, b| b.created_at.cmp(&a.created_at));

        // Apply limit
        results.into_iter().take(limit).collect()
    }

    /// Search memories by content (simple substring search for now)
    /// 
    /// TODO: Implement semantic search with embeddings
    /// 
    /// # Arguments
    /// * `query` - The search query
    /// * `filters` - Optional filter criteria
    /// * `limit` - Maximum number of results
    /// 
    /// # Returns
    /// Vector of memories matching the query
    pub fn search(
        &self,
        query: &str,
        filters: Option<&MemoryFilters>,
        limit: usize,
    ) -> Vec<&MemoryItem> {
        let query_lower = query.to_lowercase();
        let default_filters = MemoryFilters::default();
        let filters = filters.unwrap_or(&default_filters);

        let mut results: Vec<&MemoryItem> = self
            .memories
            .values()
            .filter(|memory| {
                self.matches_filters(memory, filters)
                    && memory.content.to_lowercase().contains(&query_lower)
            })
            .collect();

        // Sort by relevance (for now, just by created_at)
        results.sort_by(|a, b| b.created_at.cmp(&a.created_at));

        results.into_iter().take(limit).collect()
    }

    /// Update an existing memory
    /// 
    /// # Arguments
    /// * `memory_id` - The ID of the memory to update
    /// * `content` - Optional new content
    /// * `metadata` - Optional metadata to merge with existing
    /// 
    /// # Returns
    /// true if memory was updated, false if not found
    pub fn update(
        &mut self,
        memory_id: &str,
        content: Option<String>,
        metadata: Option<HashMap<String, serde_json::Value>>,
    ) -> bool {
        if let Some(memory) = self.memories.get_mut(memory_id) {
            if let Some(new_content) = content {
                memory.content = new_content;
            }
            if let Some(new_metadata) = metadata {
                memory.metadata.extend(new_metadata);
            }
            memory.updated_at = SystemTime::now();
            true
        } else {
            false
        }
    }

    /// Delete a memory by ID
    /// 
    /// # Arguments
    /// * `memory_id` - The ID of the memory to delete
    /// 
    /// # Returns
    /// true if memory was deleted, false if not found
    pub fn delete(&mut self, memory_id: &str) -> bool {
        self.memories.remove(memory_id).is_some()
    }

    /// Delete all memories matching the given filters
    /// 
    /// # Arguments
    /// * `filters` - Filter criteria for memories to delete
    /// 
    /// # Returns
    /// Number of memories deleted
    pub fn delete_all(&mut self, filters: &MemoryFilters) -> usize {
        let ids_to_delete: Vec<String> = self
            .memories
            .values()
            .filter(|memory| self.matches_filters(memory, filters))
            .map(|memory| memory.id.clone())
            .collect();

        let count = ids_to_delete.len();
        for id in ids_to_delete {
            self.memories.remove(&id);
        }
        count
    }

    /// Check if a memory matches the given filters
    fn matches_filters(&self, memory: &MemoryItem, filters: &MemoryFilters) -> bool {
        // Check user_id
        if let Some(ref user_id) = filters.user_id {
            if memory.user_id.as_ref() != Some(user_id) {
                return false;
            }
        }

        // Check agent_id
        if let Some(ref agent_id) = filters.agent_id {
            if memory.agent_id.as_ref() != Some(agent_id) {
                return false;
            }
        }

        // Check run_id
        if let Some(ref run_id) = filters.run_id {
            if memory.run_id.as_ref() != Some(run_id) {
                return false;
            }
        }

        // Check metadata filters
        for (key, value) in &filters.metadata {
            if memory.metadata.get(key) != Some(value) {
                return false;
            }
        }

        true
    }

    /// Get total count of memories
    pub fn count(&self) -> usize {
        self.memories.len()
    }

    /// Get count of memories matching filters
    pub fn count_filtered(&self, filters: &MemoryFilters) -> usize {
        self.memories
            .values()
            .filter(|memory| self.matches_filters(memory, filters))
            .count()
    }
}

impl Default for MemoryStore {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_and_get() {
        let mut store = MemoryStore::new();
        let id = store.add(
            "Test memory",
            Some("user_1".to_string()),
            None,
            None,
            HashMap::new(),
        );

        let memory = store.get(&id).unwrap();
        assert_eq!(memory.content, "Test memory");
        assert_eq!(memory.user_id.as_ref().unwrap(), "user_1");
    }

    #[test]
    fn test_get_all_with_filters() {
        let mut store = MemoryStore::new();
        
        store.add("Memory 1", Some("user_1".to_string()), None, None, HashMap::new());
        store.add("Memory 2", Some("user_1".to_string()), None, None, HashMap::new());
        store.add("Memory 3", Some("user_2".to_string()), None, None, HashMap::new());

        let filters = MemoryFilters {
            user_id: Some("user_1".to_string()),
            ..Default::default()
        };

        let results = store.get_all(&filters, 100);
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_search() {
        let mut store = MemoryStore::new();
        
        store.add("Patient has diabetes", Some("user_1".to_string()), None, None, HashMap::new());
        store.add("Patient has hypertension", Some("user_1".to_string()), None, None, HashMap::new());

        let results = store.search("diabetes", None, 10);
        assert_eq!(results.len(), 1);
        assert!(results[0].content.contains("diabetes"));
    }

    #[test]
    fn test_update() {
        let mut store = MemoryStore::new();
        let id = store.add("Original content", Some("user_1".to_string()), None, None, HashMap::new());

        store.update(&id, Some("Updated content".to_string()), None);

        let memory = store.get(&id).unwrap();
        assert_eq!(memory.content, "Updated content");
    }

    #[test]
    fn test_delete() {
        let mut store = MemoryStore::new();
        let id = store.add("Test memory", Some("user_1".to_string()), None, None, HashMap::new());

        assert!(store.delete(&id));
        assert!(store.get(&id).is_none());
    }
}
