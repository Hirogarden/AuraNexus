// Prevents console window on Windows (including debug builds for now)
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

mod llm;
mod memory;
mod models;
mod memory_store;  // Translated from mem0
mod text_chunker;  // Translated from llama_index
mod rag_example;   // Example usage of translated modules
mod python_bridge;  // Bridge to Python backend

use serde::{Deserialize, Serialize};
use tauri::Manager;
use std::sync::Arc;
use parking_lot::Mutex;
use python_bridge::{PythonBridge, LlmConfig, ConversationEntry, SearchResult};

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
    response: String,
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
                "You are Aura, a helpful and versatile AI assistant. You help with any task - answering questions, \
                brainstorming ideas, solving problems, providing information, or just having a conversation. \
                You're friendly, clear, and adapt to what the user needs.".to_string()
            }
            AppMode::Youniverse => {
                "You are an imaginative AI storyteller in the 'You'niverse. You craft engaging narratives, \
                develop rich characters, and help users explore creative storylines. You adapt to different genres, \
                maintain story continuity, and encourage creative expression.".to_string()
            }
        }
    }
}

// Application state with Python bridge
struct AppState {
    python_bridge: Arc<Mutex<PythonBridge>>,
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
            top_p: 0.95,
            min_p: Some(0.05),
            frequency_penalty: Some(0.2),
            presence_penalty: Some(0.1),
            dry_multiplier: Some(0.7),
            ..Default::default()
        },
        AppMode::Youniverse => LlmConfig {
            temperature: 0.85,  // More creative for storytelling
            top_p: 0.95,
            min_p: Some(0.02),
            frequency_penalty: Some(0.1),
            presence_penalty: Some(0.2),
            dry_multiplier: Some(0.5),
            ..Default::default()
        },
    };
    
    // Generate response using Python bridge
    let response_text = {
        let bridge = state.python_bridge.lock();
        bridge.generate(
            message.clone(),
            Some(system_prompt),
            history.clone(),
            config,
        ).map_err(|e| format!("Failed to generate response: {}", e))?
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
    
    // Log to hierarchical storage (The Nexus Core)
    {
        let bridge = state.python_bridge.lock();
        bridge.log_conversation(
            message,
            response_text.clone(),
            mode.to_string(),
        ).map_err(|e| format!("Failed to log conversation: {}", e))?;
    }
    
    println!("✅ Generated response ({} chars)", response_text.len());
    
    Ok(ChatResponse {
        agent: "aura".to_string(),
        response: response_text,
        timestamp,
        mode: mode.to_string(),
    })
}

// Check if LLM is ready (replaces backend health check)
#[tauri::command]
async fn check_backend(state: tauri::State<'_, AppState>) -> Result<bool, String> {
    let bridge = state.python_bridge.lock();
    bridge.check_model_exists()
        .map_err(|e| format!("Health check failed: {}", e))
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

// Search past conversations using The Nexus Core
#[tauri::command]
async fn search_conversations(
    query: String,
    top_k: usize,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<SearchResult>, String> {
    println!("🔍 Searching conversations: {}", query);
    
    let bridge = state.python_bridge.lock();
    let results = bridge.search_memory(query, top_k)
        .map_err(|e| format!("Search failed: {}", e))?;
    
    println!("✅ Found {} results", results.len());
    Ok(results)
}

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

// Initialize model (download if needed)
#[tauri::command]
async fn initialize_model(state: tauri::State<'_, AppState>) -> Result<String, String> {
    println!("🔧 Initializing model...");
    
    let bridge = state.python_bridge.lock();
    
    // Check if model exists
    let has_model = bridge.check_model_exists()
        .map_err(|e| format!("Failed to check model: {}", e))?;
    
    if !has_model {
        println!("📥 No model found, downloading starter model...");
        
        // Download starter model
        let model_path = bridge.download_starter_model(|progress| {
            println!("📊 Download progress: {:.1}%", progress * 100.0);
        }).map_err(|e| format!("Failed to download model: {}", e))?;
        
        println!("✅ Model downloaded: {}", model_path.display());
    }
    
    // Load model into memory
    bridge.load_model(None)
        .map_err(|e| format!("Failed to load model: {}", e))?;
    
    println!("✅ Model loaded and ready");
    Ok("Model initialized successfully".to_string())
}

fn main() {
    println!("🚀 Starting AuraNexus with Python Backend Integration...");
    
    // Initialize Python bridge
    println!("🐍 Initializing Python bridge...");
    let python_bridge = match PythonBridge::new() {
        Ok(bridge) => {
            println!("✅ Python bridge created");
            // Initialize Python interpreter
            {
                let mut bridge_locked = bridge.lock();
                bridge_locked.initialize()
                    .expect("Failed to initialize Python backend");
            }
            println!("✅ Python backend initialized");
            bridge
        }
        Err(e) => {
            eprintln!("❌ Failed to create Python bridge: {}", e);
            panic!("Cannot start without Python backend");
        }
    };
    
    // Create application state
    let app_state = AppState {
        python_bridge,
        conversation_history: Arc::new(Mutex::new(Vec::new())),
        current_mode: Arc::new(Mutex::new(AppMode::Companion)),  // Start in Companion mode
    };
    
    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            send_chat_message,
            check_backend,
            switch_mode,
            search_conversations,
            get_conversation_history,
            get_current_mode,
            initialize_model,
            models::get_available_models,
            models::get_model_info
        ])
        .setup(|app| {
            println!("✅ Tauri setup complete");
            let window = app.get_window("main").unwrap();
            println!("🪟 Window created: {:?}", window.label());
            
            // Trigger model initialization on startup
            let app_handle = app.app_handle();
            tauri::async_runtime::spawn(async move {
                use tauri::Manager;
                println!("🔄 Starting model initialization...");
                // Give the window time to load before showing download progress
                tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
                
                if let Some(state) = app_handle.try_state::<AppState>() {
                    match initialize_model_impl(&state).await {
                        Ok(_) => println!("✅ Model initialization complete"),
                        Err(e) => eprintln!("❌ Model initialization failed: {}", e),
                    }
                }
            });
            
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    
    println!("👋 AuraNexus closed.");
}

// Helper function for model initialization (called from setup)
async fn initialize_model_impl(state: &AppState) -> Result<(), String> {
    let bridge = state.python_bridge.lock();
    
    let has_model = bridge.check_model_exists()
        .map_err(|e| format!("Failed to check model: {}", e))?;
    
    if !has_model {
        println!("📥 No model found, downloading starter model...");
        let model_path = bridge.download_starter_model(|progress| {
            println!("📊 Download progress: {:.1}%", progress * 100.0);
        }).map_err(|e| format!("Failed to download model: {}", e))?;
        
        println!("✅ Model downloaded: {}", model_path.display());
    }
    
    bridge.load_model(None)
        .map_err(|e| format!("Failed to load model: {}", e))?;
    
    println!("✅ Model loaded and ready");
    Ok(())
}
