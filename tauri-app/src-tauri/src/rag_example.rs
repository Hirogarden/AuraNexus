// Example: Using translated modules together
// This shows how memory_store and text_chunker work together for RAG

use crate::memory_store::{MemoryStore, MemoryFilters};
use crate::text_chunker::{TextChunker, ChunkingConfig};
use std::collections::HashMap;

/// Example: Document ingestion with memory storage
/// 
/// This demonstrates how to:
/// 1. Chunk a large document
/// 2. Store chunks in memory with metadata
/// 3. Retrieve relevant chunks for a query
pub fn ingest_document(
    document: &str,
    doc_id: &str,
    user_id: &str,
    store: &mut MemoryStore,
) -> Vec<String> {
    // Step 1: Chunk the document
    let chunker = TextChunker::with_config(ChunkingConfig {
        chunk_size: 512,
        chunk_overlap: 50,
        ..Default::default()
    });
    
    let chunks = chunker.chunk_with_metadata(document);
    let chunk_count = chunks.len();
    println!("📄 Split document into {} chunks", chunk_count);
    
    // Step 2: Store each chunk with metadata
    let mut chunk_ids = Vec::new();
    for (chunk_text, idx) in chunks {
        let mut metadata = HashMap::new();
        metadata.insert("doc_id".to_string(), serde_json::json!(doc_id));
        metadata.insert("chunk_index".to_string(), serde_json::json!(idx));
        metadata.insert("chunk_count".to_string(), serde_json::json!(chunk_count));
        
        let chunk_id = store.add(
            chunk_text,
            Some(user_id.to_string()),
            None,
            None,
            metadata,
        );
        chunk_ids.push(chunk_id);
    }
    
    println!("💾 Stored {} chunks in memory", chunk_ids.len());
    chunk_ids
}

/// Example: Retrieve relevant document chunks
/// 
/// Demonstrates simple keyword search (TODO: upgrade to semantic search)
pub fn retrieve_chunks(
    query: &str,
    user_id: &str,
    store: &MemoryStore,
    top_k: usize,
) -> Vec<String> {
    let filters = MemoryFilters {
        user_id: Some(user_id.to_string()),
        ..Default::default()
    };
    
    // Search for relevant chunks
    let results = store.search(query, Some(&filters), top_k);
    
    println!("🔍 Found {} relevant chunks for query: {}", results.len(), query);
    
    results.iter().map(|mem| mem.content.clone()).collect()
}

/// Example: RAG-style question answering
/// 
/// This is a basic pattern - full implementation would:
/// 1. Generate embeddings for semantic search
/// 2. Use retrieved chunks as context for LLM
/// 3. Cite sources in response
pub fn answer_question(
    question: &str,
    user_id: &str,
    store: &MemoryStore,
) -> String {
    // Retrieve relevant context
    let context_chunks = retrieve_chunks(question, user_id, store, 3);
    
    if context_chunks.is_empty() {
        return "I don't have enough information to answer that.".to_string();
    }
    
    // Build context for LLM
    let _context = context_chunks.join("\n\n");
    
    // TODO: Send to LLM with prompt:
    // "Based on the following context, answer the question.
    //  Context: {context}
    //  Question: {question}
    //  Answer:"
    
    format!("Context retrieved ({} chunks). Ready for LLM.", context_chunks.len())
}

/// Example: Medical conversation memory
/// 
/// Demonstrates session-scoped memory for healthcare conversations
pub fn medical_conversation_example() {
    let mut store = MemoryStore::new();
    let patient_id = "patient_123";
    let agent_id = "medical_assistant";
    
    // Store conversation turns
    store.add(
        "Patient reports fever of 101°F for 2 days",
        Some(patient_id.to_string()),
        Some(agent_id.to_string()),
        Some("session_2024_001".to_string()),
        HashMap::new(),
    );
    
    store.add(
        "Patient has history of type 2 diabetes",
        Some(patient_id.to_string()),
        Some(agent_id.to_string()),
        Some("session_2024_001".to_string()),
        HashMap::new(),
    );
    
    // Retrieve all memories for this patient+agent
    let filters = MemoryFilters {
        user_id: Some(patient_id.to_string()),
        agent_id: Some(agent_id.to_string()),
        ..Default::default()
    };
    
    let memories = store.get_all(&filters, 100);
    println!("📋 Retrieved {} memories for patient", memories.len());
    
    for memory in memories {
        println!("  - {}", memory.content);
    }
}

/// Example: Document Q&A with chunking and retrieval
pub fn document_qa_example() {
    let mut store = MemoryStore::new();
    let user_id = "user_1";
    
    // Sample medical document
    let document = r#"
        Type 2 diabetes is a chronic condition that affects the way the body processes blood sugar (glucose). 
        With type 2 diabetes, the body either resists the effects of insulin or doesn't produce enough insulin 
        to maintain normal glucose levels.
        
        Symptoms include increased thirst, frequent urination, hunger, fatigue, and blurred vision. 
        Treatment typically involves lifestyle changes, monitoring blood sugar, diabetes medications, 
        and sometimes insulin therapy.
        
        Complications can include cardiovascular disease, nerve damage, kidney damage, eye damage, 
        and slow healing. Prevention involves healthy eating, regular physical activity, 
        and maintaining a healthy weight.
    "#;
    
    // Ingest document
    println!("\n=== Document Ingestion ===");
    let _chunk_ids = ingest_document(document, "diabetes_guide", user_id, &mut store);
    
    // Ask questions
    println!("\n=== Question 1: What are the symptoms? ===");
    answer_question("What are the symptoms of type 2 diabetes?", user_id, &store);
    
    println!("\n=== Question 2: How is it treated? ===");
    answer_question("How is type 2 diabetes treated?", user_id, &store);
    
    println!("\n=== Question 3: What are complications? ===");
    answer_question("What complications can occur?", user_id, &store);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ingest_and_retrieve() {
        let mut store = MemoryStore::new();
        let user_id = "test_user";
        
        let document = "This is a test document. It has multiple sentences. We will chunk it and store it.";
        
        let chunk_ids = ingest_document(document, "test_doc", user_id, &mut store);
        assert!(!chunk_ids.is_empty());
        
        let results = retrieve_chunks("test document", user_id, &store, 5);
        assert!(!results.is_empty());
    }
    
    #[test]
    fn test_medical_memory() {
        medical_conversation_example();
        // If it doesn't panic, it works
    }
}
