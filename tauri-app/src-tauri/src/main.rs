// Prevents additional console window on Windows in release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use tauri::Manager;

#[derive(Debug, Serialize, Deserialize)]
struct ChatRequest {
    message: String,
    target_agent: Option<String>,
    session_id: Option<String>,
    conversation_type: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ChatResponse {
    agent: String,
    response: String,
    timestamp: Option<String>,
}

// Send message to Python backend
#[tauri::command]
async fn send_chat_message(message: String, agent: Option<String>) -> Result<ChatResponse, String> {
    let client = reqwest::Client::new();
    
    let request = ChatRequest {
        message,
        target_agent: agent,
        session_id: None,
        conversation_type: Some("general".to_string()),
    };
    
    match client
        .post("http://127.0.0.1:8000/chat")
        .json(&request)
        .send()
        .await
    {
        Ok(response) => {
            match response.json::<ChatResponse>().await {
                Ok(data) => Ok(data),
                Err(e) => Err(format!("Failed to parse response: {}", e)),
            }
        }
        Err(e) => Err(format!("Backend connection failed: {}", e)),
    }
}

// Check backend health
#[tauri::command]
async fn check_backend() -> Result<bool, String> {
    let client = reqwest::Client::new();
    
    match client.get("http://127.0.0.1:8000/").send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            send_chat_message,
            check_backend
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
