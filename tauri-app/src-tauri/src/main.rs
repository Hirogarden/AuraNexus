// Prevents console window on Windows (including debug builds for now)
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

mod llm;
mod memory;
mod models;
mod memory_store;  // Translated from mem0
mod text_chunker;  // Translated from llama_index
mod rag_example;   // Example usage of translated modules

use serde::{Deserialize, Serialize};
use tauri::Manager;
use tokio::sync::{mpsc, oneshot};
use std::sync::Arc;
use parking_lot::Mutex;

#[derive(Debug, Serialize, Deserialize)]
struct ChatResponse {
    agent: String,
    response: String,
    timestamp: Option<String>,
}

// Message types for LLM worker communication
struct LlmRequest {
    prompt: String,
    response_tx: oneshot::Sender<Result<String, String>>,
}

enum WorkerMessage {
    Generate(LlmRequest),
    CheckHealth(oneshot::Sender<bool>),
    Shutdown,
}

// Application state - just holds the channel sender
struct AppState {
    llm_tx: mpsc::UnboundedSender<WorkerMessage>,
    memory: Arc<Mutex<memory::MemoryManager>>,
}

// Send message using native Rust LLM (no HTTP, no external processes)
#[tauri::command]
async fn send_chat_message(
    message: String,
    agent: Option<String>,
    conversation_type: Option<String>,
    system_prompt: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<ChatResponse, String> {
    println!("📩 Received message in {} mode", conversation_type.as_deref().unwrap_or("general"));
    
    // Get conversation context from memory
    let memory_context = {
        let memory = state.memory.lock();
        memory.get_recent_context(5)
    };
    
    // Build prompt with Llama 3.1 chat format
    let system_prompt = system_prompt.unwrap_or_else(|| {
        "You are Aura, a friendly and helpful AI assistant.".to_string()
    });
    
    // Llama 3.1 Instruct format:
    // <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    // {system}<|eot_id|><|start_header_id|>user<|end_header_id|>
    // {prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
    let full_prompt = format!(
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{}\n\nRecent conversation:\n{}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
        system_prompt,
        memory_context,
        message
    );
    
    // Send request to LLM worker via channel
    let (response_tx, response_rx) = oneshot::channel();
    let request = LlmRequest {
        prompt: full_prompt,
        response_tx,
    };
    
    state.llm_tx.send(WorkerMessage::Generate(request))
        .map_err(|_| "LLM worker unavailable".to_string())?;
    
    // Wait for response from worker
    let response = response_rx.await
        .map_err(|_| "LLM worker disconnected".to_string())??;
    
    // Save to memory
    {
        let mut memory = state.memory.lock();
        memory.add_message("user", &message);
        memory.add_message("assistant", &response);
    }
    
    println!("✅ Generated response ({} chars)", response.len());
    
    Ok(ChatResponse {
        agent: agent.unwrap_or_else(|| "narrator".to_string()),
        response,
        timestamp: Some(chrono::Utc::now().to_rfc3339()),
    })
}

// Check if LLM is ready (replaces backend health check)
#[tauri::command]
async fn check_backend(state: tauri::State<'_, AppState>) -> Result<bool, String> {
    let (tx, rx) = oneshot::channel();
    
    state.llm_tx.send(WorkerMessage::CheckHealth(tx))
        .map_err(|_| "LLM worker unavailable".to_string())?;
    
    rx.await.map_err(|_| "LLM worker disconnected".to_string())
}

// LLM worker thread - owns the LLM and processes requests
fn spawn_llm_worker() -> mpsc::UnboundedSender<WorkerMessage> {
    let (tx, mut rx) = mpsc::unbounded_channel();
    
    std::thread::spawn(move || {
        println!("🔧 LLM worker thread starting...");
        
        // Initialize LLM in this dedicated thread
        let mut llm = match llm::LlmManager::new() {
            Ok(llm) => {
                println!("✅ LLM loaded successfully in worker thread");
                llm
            }
            Err(e) => {
                eprintln!("❌ Failed to load LLM: {}", e);
                return;
            }
        };
        
        // Process messages from channel
        while let Some(msg) = rx.blocking_recv() {
            match msg {
                WorkerMessage::Generate(request) => {
                    println!("🤖 Processing generation request...");
                    let result = llm.generate(&request.prompt)
                        .map_err(|e| format!("Generation failed: {}", e));
                    
                    // Send response back (ignore if receiver dropped)
                    let _ = request.response_tx.send(result);
                }
                WorkerMessage::CheckHealth(response_tx) => {
                    let _ = response_tx.send(llm.is_ready());
                }
                WorkerMessage::Shutdown => {
                    println!("👋 LLM worker shutting down...");
                    break;
                }
            }
        }
        
        println!("🛑 LLM worker thread stopped");
    });
    
    tx
}

fn main() {
    println!("🚀 Starting AuraNexus (Native Rust)...");
    
    // Spawn LLM worker thread
    let llm_tx = spawn_llm_worker();
    
    // Initialize memory system
    println!("🧠 Initializing memory system...");
    let memory = Arc::new(Mutex::new(memory::MemoryManager::new()));
    println!("✅ Memory system ready");
    
    let app_state = AppState { llm_tx, memory };
    
    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            send_chat_message,
            check_backend,
            models::get_available_models,
            models::get_model_info
        ])
        .setup(|app| {
            println!("✅ Tauri setup complete");
            let window = app.get_window("main").unwrap();
            println!("🪟 Window created: {:?}", window.label());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    
    println!("👋 AuraNexus closed.");
}
