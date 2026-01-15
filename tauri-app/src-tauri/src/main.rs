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
    system_prompt: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ChatResponse {
    agent: String,
    response: String,
    timestamp: Option<String>,
}

// Send message to Python backend
#[tauri::command]
async fn send_chat_message(message: String, agent: Option<String>, conversation_type: Option<String>, system_prompt: Option<String>) -> Result<ChatResponse, String> {
    let client = reqwest::Client::new();
    
    let request = ChatRequest {
        message,
        target_agent: agent,
        session_id: None,
        conversation_type: conversation_type.or(Some("general".to_string())),
        system_prompt,
    };
    
    match client
        .post("http://localhost:8000/chat")
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
    
    match client.get("http://localhost:8000/").send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false),
    }
}

fn main() {
    println!("Starting Tauri application...");
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            send_chat_message,
            check_backend
        ])
        .setup(|app| {
            println!("Tauri setup complete");
            let window = app.get_window("main").unwrap();
            println!("Window created: {:?}", window.label());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    println!("Tauri application closed.");
}
