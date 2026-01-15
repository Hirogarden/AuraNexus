use std::collections::VecDeque;
use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Message {
    role: String,
    content: String,
    timestamp: DateTime<Utc>,
}

pub struct MemoryManager {
    messages: VecDeque<Message>,
    max_messages: usize,
}

impl MemoryManager {
    pub fn new() -> Self {
        Self {
            messages: VecDeque::new(),
            max_messages: 50, // Keep last 50 messages in memory
        }
    }
    
    pub fn add_message(&mut self, role: &str, content: &str) {
        let message = Message {
            role: role.to_string(),
            content: content.to_string(),
            timestamp: Utc::now(),
        };
        
        self.messages.push_back(message);
        
        // Trim old messages
        while self.messages.len() > self.max_messages {
            self.messages.pop_front();
        }
    }
    
    pub fn get_recent_context(&self, n: usize) -> String {
        self.messages
            .iter()
            .rev()
            .take(n)
            .rev()
            .map(|msg| format!("{}: {}", msg.role, msg.content))
            .collect::<Vec<_>>()
            .join("\n")
    }
    
    pub fn clear(&mut self) {
        self.messages.clear();
    }
    
    pub fn message_count(&self) -> usize {
        self.messages.len()
    }
}

// TODO: Add vector embeddings and semantic search for RAG
// Will implement this with a Rust embedding model and in-memory vector store
