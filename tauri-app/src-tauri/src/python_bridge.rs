use anyhow::{Context, Result};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Arc;
use parking_lot::Mutex;

/// Python backend bridge - connects Tauri to existing Python LLM infrastructure
/// This enables use of advanced sampling, The Nexus Core, and all Phase 1 features
pub struct PythonBridge {
    backend_path: PathBuf,
    initialized: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LlmConfig {
    pub temperature: f32,
    pub top_p: f32,
    pub top_k: i32,
    pub min_p: Option<f32>,
    pub frequency_penalty: Option<f32>,
    pub presence_penalty: Option<f32>,
    pub dry_multiplier: Option<f32>,
    pub xtc_probability: Option<f32>,
    pub dynatemp_range: Option<f32>,
    pub max_tokens: i32,
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationEntry {
    pub role: String,
    pub content: String,
    pub timestamp: String,
    pub quality_score: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub content: String,
    pub timestamp: String,
    pub relevance_score: f32,
    pub citations: Vec<String>,
}

impl PythonBridge {
    /// Create new Python bridge instance
    pub fn new() -> Result<Arc<Mutex<Self>>> {
        // Find backend path (relative to executable or development location)
        let backend_path = Self::find_backend_path()
            .context("Failed to find Python backend directory")?;
        
        println!("🐍 Python backend path: {}", backend_path.display());
        
        Ok(Arc::new(Mutex::new(Self {
            backend_path,
            initialized: false,
        })))
    }
    
    /// Find the Python backend directory
    fn find_backend_path() -> Option<PathBuf> {
        let current_dir = std::env::current_dir().ok()?;
        println!("🔍 Current directory: {}", current_dir.display());
        
        // Try multiple locations
        let search_paths = vec![
            // Development: from tauri-app/src-tauri
            current_dir.parent()?.parent()?.join("electron-app").join("backend"),
            // Alternative: if running from tauri-app
            current_dir.parent()?.join("electron-app").join("backend"),
            // Alternative: if running from workspace root
            current_dir.join("electron-app").join("backend"),
            // Production: bundled with exe
            std::env::current_exe().ok()?.parent()?.join("backend"),
        ];
        
        for path in &search_paths {
            println!("🔍 Checking path: {}", path.display());
            if path.exists() && path.join("llm_manager.py").exists() {
                println!("✅ Found backend at: {}", path.display());
                return Some(path.clone());
            }
        }
        
        println!("❌ Could not find Python backend in any search path");
        
        None
    }
    
    /// Initialize Python interpreter and import backend modules
    pub fn initialize(&mut self) -> Result<()> {
        if self.initialized {
            return Ok(());
        }
        
        println!("🐍 Initializing Python interpreter...");
        println!("🐍 Backend path: {}", self.backend_path.display());
        
        let result = Python::with_gil(|py| {
            // Add backend path to sys.path
            println!("🐍 Adding backend to sys.path...");
            let sys = py.import("sys")?;
            let path = sys.getattr("path")?;
            path.call_method1("insert", (0, self.backend_path.to_str().unwrap()))?;
            
            // Also add parent directory (for nexus_core_* modules)
            if let Some(parent) = self.backend_path.parent()?.parent() {
                println!("🐍 Adding workspace root to sys.path: {}", parent.display());
                path.call_method1("insert", (0, parent.to_str().unwrap()))?;
            }
            
            // Import backend modules to verify they load
            println!("🐍 Importing llm_manager...");
            let _llm_manager = py.import("llm_manager").map_err(|e| {
                println!("❌ Failed to import llm_manager: {}", e);
                e
            })?;
            
            println!("🐍 Importing hierarchical_memory...");
            let _memory_manager = py.import("hierarchical_memory").map_err(|e| {
                println!("❌ Failed to import hierarchical_memory: {}", e);
                e
            })?;
            
            println!("✅ Python backend modules loaded successfully");
            Ok::<(), PyErr>(())
        });
        
        match result {
            Ok(_) => {
                self.initialized = true;
                println!("✅ Python bridge initialization complete");
                Ok(())
            }
            Err(e) => {
                println!("❌ Python initialization failed: {}", e);
                Err(anyhow::anyhow!("Failed to initialize Python backend: {}", e))
            }
        }
    }
    
    /// Check if a model exists or needs to be downloaded
    pub fn check_model_exists(&self) -> Result<bool> {
        let result = Python::with_gil(|py| {
            let llm_manager = py.import("llm_manager")?;
            let find_model = llm_manager.getattr("find_available_model")?;
            let result = find_model.call0()?;
            
            // Returns model path or None
            Ok::<bool, PyErr>(!result.is_none())
        });
        
        result.context("Failed to check model existence")
    }
    
    /// Download starter model (Qwen2.5-0.5B-Instruct)
    pub fn download_starter_model(&self, _progress_callback: impl Fn(f32) + Send + 'static) -> Result<PathBuf> {
        let result = Python::with_gil(|py| {
            let llm_manager = py.import("llm_manager")?;
            let download_fn = llm_manager.getattr("download_starter_model")?;
            
            // Call download function (blocking)
            let model_path = download_fn.call0()?;
            let path_str: String = model_path.extract()?;
            
            Ok::<PathBuf, PyErr>(PathBuf::from(path_str))
        });
        
        result.context("Failed to download starter model")
    }
    
    /// Load model into memory
    pub fn load_model(&self, model_path: Option<PathBuf>) -> Result<()> {
        let result = Python::with_gil(|py| {
            let llm_manager = py.import("llm_manager")?;
            let load_fn = llm_manager.getattr("load_model")?;
            
            if let Some(path) = model_path {
                load_fn.call1((path.to_str().unwrap(),))?;
            } else {
                // Auto-find model
                let find_model = llm_manager.getattr("find_available_model")?;
                let model_path_py = find_model.call0()?;
                
                if model_path_py.is_none() {
                    return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>("No model found"));
                }
                
                load_fn.call1((model_path_py,))?;
            }
            
            Ok::<(), PyErr>(())
        });
        
        result.context("Failed to load model")
    }
    
    /// Generate response using Python LLM with advanced sampling
    pub fn generate(
        &self,
        prompt: String,
        system_prompt: Option<String>,
        conversation_history: Vec<ConversationEntry>,
        config: LlmConfig,
    ) -> Result<String> {
        let result = Python::with_gil(|py| {
            let llm_manager = py.import("llm_manager")?;
            let generate_fn = llm_manager.getattr("generate_with_context")?;
            
            // Build kwargs dict with sampling parameters
            let kwargs = PyDict::new(py);
            kwargs.set_item("prompt", prompt)?;
            kwargs.set_item("temperature", config.temperature)?;
            kwargs.set_item("top_p", config.top_p)?;
            kwargs.set_item("top_k", config.top_k)?;
            kwargs.set_item("max_tokens", config.max_tokens)?;
            
            if let Some(min_p) = config.min_p {
                kwargs.set_item("min_p", min_p)?;
            }
            if let Some(freq) = config.frequency_penalty {
                kwargs.set_item("frequency_penalty", freq)?;
            }
            if let Some(pres) = config.presence_penalty {
                kwargs.set_item("presence_penalty", pres)?;
            }
            if let Some(dry) = config.dry_multiplier {
                kwargs.set_item("dry_multiplier", dry)?;
            }
            if let Some(xtc) = config.xtc_probability {
                kwargs.set_item("xtc_probability", xtc)?;
            }
            if let Some(dynatemp) = config.dynatemp_range {
                kwargs.set_item("dynatemp_range", dynatemp)?;
            }
            
            if let Some(sys_prompt) = system_prompt {
                kwargs.set_item("system_prompt", sys_prompt)?;
            }
            
            // Convert conversation history to Python list of dicts
            let history_list = pyo3::types::PyList::empty(py);
            for entry in conversation_history {
                let entry_dict = PyDict::new(py);
                entry_dict.set_item("role", entry.role)?;
                entry_dict.set_item("content", entry.content)?;
                entry_dict.set_item("timestamp", entry.timestamp)?;
                history_list.append(entry_dict)?;
            }
            kwargs.set_item("conversation_history", history_list)?;
            
            // Call generate function
            let response = generate_fn.call((), Some(kwargs))?;
            let response_text: String = response.extract()?;
            
            Ok::<String, PyErr>(response_text)
        });
        
        result.context("Failed to generate response")
    }
    
    /// Log conversation turn to hierarchical storage
    /// Log conversation turn to hierarchical storage
    pub fn log_conversation(
        &self,
        user_message: String,
        assistant_response: String,
        mode: String,
    ) -> Result<()> {
        let result = Python::with_gil(|py| {
            let nexus_engine = py.import("nexus_core_engine")?;
            let log_fn = nexus_engine.getattr("log_conversation_turn")?;
            
            log_fn.call1((user_message, assistant_response, mode))?;
            
            Ok::<(), PyErr>(())
        });
        
        result.context("Failed to log conversation")
    }
    
    /// Search past conversations using The Nexus Core
    pub fn search_memory(&self, query: String, top_k: usize) -> Result<Vec<SearchResult>> {
        let result = Python::with_gil(|py| {
            let nexus_indexing = py.import("nexus_core_indexing")?;
            let search_fn = nexus_indexing.getattr("intelligent_search")?;
            
            let results_py = search_fn.call1((query, top_k))?;
            
            // Convert Python list to Rust Vec
            let results_list: &pyo3::types::PyList = results_py.downcast()?;
            let mut results = Vec::new();
            
            for item in results_list.iter() {
                let dict: &PyDict = item.downcast()?;
                let result = SearchResult {
                    content: dict.get_item("content")?.unwrap().extract()?,
                    timestamp: dict.get_item("timestamp")?.unwrap().extract()?,
                    relevance_score: dict.get_item("relevance_score")?.unwrap().extract()?,
                    citations: dict.get_item("citations")?.unwrap().extract()?,
                };
                results.push(result);
            }
            
            Ok::<Vec<SearchResult>, PyErr>(results)
        });
        
        result.context("Failed to search memory")
    }
    
    /// Get recent conversation history
    pub fn get_conversation_history(&self, limit: usize) -> Result<Vec<ConversationEntry>> {
        let result = Python::with_gil(|py| {
            let memory_manager = py.import("hierarchical_memory")?;
            let get_history_fn = memory_manager.getattr("get_recent_history")?;
            
            let history_py = get_history_fn.call1((limit,))?;
            
            // Convert Python list to Rust Vec
            let history_list: &pyo3::types::PyList = history_py.downcast()?;
            let mut history = Vec::new();
            
            for item in history_list.iter() {
                let dict: &PyDict = item.downcast()?;
                let entry = ConversationEntry {
                    role: dict.get_item("role")?.unwrap().extract()?,
                    content: dict.get_item("content")?.unwrap().extract()?,
                    timestamp: dict.get_item("timestamp")?.unwrap().extract()?,
                    quality_score: dict.get_item("quality_score")?.and_then(|v| v.extract().ok()),
                };
                history.push(entry);
            }
            
            Ok::<Vec<ConversationEntry>, PyErr>(history)
        });
        
        result.context("Failed to get conversation history")
    }
}
