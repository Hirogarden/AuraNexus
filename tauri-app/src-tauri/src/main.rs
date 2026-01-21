// Prevents console window on Windows (including debug builds for now)
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

mod llm;
mod memory;
mod models;
mod memory_store;  // Translated from mem0
mod text_chunker;  // Translated from llama_index
mod rag_example;   // Example usage of translated modules
// mod python_bridge;  // Not needed - using HTTP instead

use serde::{Deserialize, Serialize};
use tauri::Manager;
use std::sync::Arc;
use parking_lot::Mutex;
// use python_bridge::{PythonBridge, LlmConfig, ConversationEntry, SearchResult};

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ConversationEntry {
    role: String,
    content: String,
    timestamp: String,
    quality_score: Option<f32>,
}

#[derive(Debug)]
struct LlmConfig {
    temperature: f32,
    top_p: f32,
    top_k: i32,
    min_p: Option<f32>,
    frequency_penalty: Option<f32>,
    presence_penalty: Option<f32>,
    dry_multiplier: Option<f32>,
    xtc_probability: Option<f32>,
    dynatemp_range: Option<f32>,
    max_tokens: i32,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            temperature: 0.7,
            top_p: 0.95,
            top_k: 40,
            min_p: Some(0.05),
            frequency_penalty: Some(0.2),
            presence_penalty: Some(0.1),
            dry_multiplier: Some(0.7),
            xtc_probability: None,
            dynatemp_range: None,
            max_tokens: 512,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ChatMessage {
    role: String,
    content: String,
    timestamp: String,
    quality_score: Option<f32>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ChatResponse {
    agent: String,
    message: String,
    timestamp: String,
    mode: String,
}

#[derive(Debug, Clone)]
enum AppMode {
    Companion,
    Youniverse,
}

impl AppMode {
    fn to_string(&self) -> String {
        match self {
            AppMode::Companion => "companion".to_string(),
            AppMode::Youniverse => "youniverse".to_string(),
        }
    }
    
    fn system_prompt(&self) -> String {
        match self {
            AppMode::Companion => {
                "You are Aura, a helpful AI assistant. Keep responses clear, concise, and helpful. \
                Answer questions directly and stay on topic.".to_string()
            }
            AppMode::Youniverse => {
                "You are a creative storyteller. Write engaging narratives in English. \
                Stay consistent with the story and respond in the same language as the user. \
                Keep responses focused and creative.".to_string()
            }
        }
    }
}

// Application state (no Python bridge needed - using HTTP)
struct AppState {
    conversation_history: Arc<Mutex<Vec<ConversationEntry>>>,
    current_mode: Arc<Mutex<AppMode>>,
}

// Send message using Python backend with advanced sampling
#[tauri::command]
async fn send_chat_message(
    message: String,
    state: tauri::State<'_, AppState>,
) -> Result<ChatResponse, String> {
    println!("📩 Received message");
    
    // Get current mode and its system prompt
    let (mode, system_prompt) = {
        let current_mode = state.current_mode.lock();
        (current_mode.clone(), current_mode.system_prompt())
    };
    
    // Get conversation history
    let history = {
        state.conversation_history.lock().clone()
    };
    
    // Get appropriate LLM config for mode
    let config = match mode {
        AppMode::Companion => LlmConfig {
            temperature: 0.7,
            top_p: 0.9,
            top_k: 50,
            min_p: Some(0.05),
            frequency_penalty: Some(0.3),
            presence_penalty: Some(0.1),
            dry_multiplier: Some(0.8),
            max_tokens: 256,  // Keep responses concise
            ..Default::default()
        },
        AppMode::Youniverse => LlmConfig {
            temperature: 0.75,  // Creative but not too wild
            top_p: 0.9,
            top_k: 60,
            min_p: Some(0.03),
            frequency_penalty: Some(0.2),
            presence_penalty: Some(0.15),
            dry_multiplier: Some(0.6),
            max_tokens: 384,  // Longer for storytelling
            ..Default::default()
        },
    };
    
    // Generate response using HTTP call to Python LLM server
    let response_text = {
        // Prepare request body
        let request_body = serde_json::json!({
            "prompt": message,
            "system_prompt": system_prompt,
            "conversation_history": history.iter().map(|entry| {
                serde_json::json!({
                    "role": entry.role,
                    "content": entry.content,
                    "timestamp": entry.timestamp
                })
            }).collect::<Vec<_>>(),
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "max_tokens": config.max_tokens,
        });
        
        // Call LLM server
        let client = reqwest::blocking::Client::new();
        let response = client
            .post("http://localhost:5555/generate")
            .json(&request_body)
            .send()
            .map_err(|e| format!("Failed to connect to LLM server: {}. Is llm_server.py running?", e))?;
        
        if !response.status().is_success() {
            return Err(format!("LLM server returned error: {}", response.status()).into());
        }
        
        let result: serde_json::Value = response.json()
            .map_err(|e| format!("Failed to parse LLM response: {}", e))?;
        
        result["response"].as_str()
            .ok_or("Missing response field in LLM output")?
            .to_string()
    };
    
    let timestamp = chrono::Utc::now().to_rfc3339();
    
    // Add to conversation history
    {
        let mut history = state.conversation_history.lock();
        history.push(ConversationEntry {
            role: "user".to_string(),
            content: message.clone(),
            timestamp: timestamp.clone(),
            quality_score: None,
        });
        history.push(ConversationEntry {
            role: "assistant".to_string(),
            content: response_text.clone(),
            timestamp: timestamp.clone(),
            quality_score: None,
        });
        
        // Keep only last 20 messages in memory
        let history_len = history.len();
        if history_len > 20 {
            history.drain(0..history_len - 20);
        }
    }
    
    // Log to hierarchical storage (The Nexus Core) - Disabled in mock mode
    // TODO: Re-enable when real LLM and persistence is set up
    // {
    //     let bridge = state.python_bridge.lock();
    //     bridge.log_conversation(
    //         message,
    //         response_text.clone(),
    //         mode.to_string(),
    //     ).map_err(|e| format!("Failed to log conversation: {}", e))?;
    // }
    
    println!("✅ Generated response ({} chars)", response_text.len());
    
    Ok(ChatResponse {
        agent: "aura".to_string(),
        message: response_text,
        timestamp,
        mode: mode.to_string(),
    })
}

// Check if LLM is ready (HTTP health check)
#[tauri::command]
async fn check_backend(_state: tauri::State<'_, AppState>) -> Result<bool, String> {
    // Check if LLM server is reachable
    match reqwest::blocking::Client::new()
        .get("http://localhost:5555/health")
        .send() 
    {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false), // Server not running
    }
}

// Switch between Companion/Youniverse modes
#[tauri::command]
async fn switch_mode(
    new_mode: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    let mode = match new_mode.as_str() {
        "companion" => AppMode::Companion,
        "youniverse" => AppMode::Youniverse,
        _ => return Err(format!("Unknown mode: {}", new_mode)),
    };
    
    {
        let mut current_mode = state.current_mode.lock();
        *current_mode = mode.clone();
    }
    
    // Clear conversation history when switching modes
    {
        let mut history = state.conversation_history.lock();
        history.clear();
    }
    
    println!("🔄 Switched to {} mode", new_mode);
    Ok(new_mode)
}

// Search past conversations using The Nexus Core (Disabled - HTTP mode)
// #[tauri::command]
// async fn search_conversations(
//     query: String,
//     top_k: usize,
//     state: tauri::State<'_, AppState>,
// ) -> Result<Vec<SearchResult>, String> {
//     println!("🔍 Searching conversations: {}", query);
//     // TODO: Implement HTTP endpoint for search
//     Ok(vec![])
// }

// Get recent conversation history
#[tauri::command]
async fn get_conversation_history(
    limit: usize,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<ChatMessage>, String> {
    let history = state.conversation_history.lock();
    
    let messages: Vec<ChatMessage> = history.iter()
        .rev()
        .take(limit)
        .rev()
        .map(|entry| ChatMessage {
            role: entry.role.clone(),
            content: entry.content.clone(),
            timestamp: entry.timestamp.clone(),
            quality_score: entry.quality_score,
        })
        .collect();
    
    Ok(messages)
}

// Get current mode
#[tauri::command]
async fn get_current_mode(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mode = state.current_mode.lock();
    Ok(mode.to_string())
}

// Initialize model (download if needed) - Disabled in HTTP mode
// #[tauri::command]
// async fn initialize_model(_state: tauri::State<'_, AppState>) -> Result<String, String> {
//     println!("🔧 Model initialization handled by Python server");
//     Ok("Model managed by llm_server.py".to_string())
// }

fn main() {
    println!("🚀 Starting AuraNexus with HTTP LLM Server...");
    
    // Note: Python LLM server should be running separately on localhost:5555
    // Start it with: python llm_server.py
    
    // Create application state (no Python bridge needed - using HTTP instead)
    let app_state = AppState {
        conversation_history: Arc::new(Mutex::new(Vec::new())),
        current_mode: Arc::new(Mutex::new(AppMode::Companion)),  // Start in Companion mode
    };
    
    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            send_chat_message,
            check_backend,
            switch_mode,
            get_conversation_history,
            get_current_mode,
            models::get_available_models,
            models::get_model_info
        ])
        .setup(|app| {
            println!("✅ Tauri setup complete");
            let window = app.get_window("main").unwrap();
            println!("🪟 Window created: {:?}", window.label());
            
            // Note: Model initialization happens in Python server (llm_server.py)
            println!("💡 Start Python server: python llm_server.py");
            
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    
    println!("👋 AuraNexus closed.");
}
