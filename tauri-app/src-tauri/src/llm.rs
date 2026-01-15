use anyhow::{Context, Result};
use llama_cpp_2::context::params::LlamaContextParams;
use llama_cpp_2::llama_backend::LlamaBackend;
use llama_cpp_2::llama_batch::LlamaBatch;
use llama_cpp_2::model::{LlamaModel, params::LlamaModelParams, Special};
use llama_cpp_2::context::LlamaContext;
use llama_cpp_2::sampling::LlamaSampler;
use std::path::PathBuf;

pub struct LlmManager {
    backend: LlamaBackend,
    model: LlamaModel,
    n_ctx: u32,
}

impl LlmManager {
    pub fn new() -> Result<Self> {
        // Initialize llama.cpp backend
        let backend = LlamaBackend::init()
            .context("Failed to initialize llama backend")?;
        
        // Find model file
        let model_path = Self::find_model()
            .context("No model found in models/ directory")?;
        
        println!("📦 Loading model: {}", model_path.display());
        
        // Load model with GPU support
        let mut model_params = LlamaModelParams::default();
        // Try to offload all layers to GPU if available (will fall back to CPU if no GPU)
        model_params = model_params.with_n_gpu_layers(999);
        
        let model = LlamaModel::load_from_file(&backend, &model_path, &model_params)
            .context("Failed to load model")?;
        
        let n_ctx = 4096; // Context window size
        
        println!("✅ Model loaded (context: {} tokens)", n_ctx);
        
        Ok(Self {
            backend,
            model,
            n_ctx,
        })
    }
    
    fn find_model() -> Option<PathBuf> {
        let models_dir = std::env::current_dir()
            .ok()?
            .parent()?
            .parent()?
            .join("models");
        
        if !models_dir.exists() {
            return None;
        }
        
        // Look for .gguf files
        std::fs::read_dir(&models_dir)
            .ok()?
            .filter_map(|entry| entry.ok())
            .filter(|entry| {
                entry.path().extension()
                    .and_then(|ext| ext.to_str())
                    .map(|ext| ext.eq_ignore_ascii_case("gguf"))
                    .unwrap_or(false)
            })
            .map(|entry| entry.path())
            .next()
    }
    
    pub fn generate(&mut self, prompt: &str) -> Result<String> {
        // Create context for this generation
        let context_params = LlamaContextParams::default()
            .with_n_ctx(Some(std::num::NonZeroU32::new(self.n_ctx).unwrap()));
        
        let mut context = self.model.new_context(&self.backend, context_params)
            .context("Failed to create context")?;
        
        // Tokenize prompt
        let tokens = self.model
            .str_to_token(prompt, llama_cpp_2::model::AddBos::Always)
            .context("Failed to tokenize prompt")?;
        
        if tokens.is_empty() {
            return Err(anyhow::anyhow!("Tokenization produced no tokens"));
        }
        
        println!("🔢 Prompt tokenized: {} tokens", tokens.len());
        
        // Create batch with size to fit all prompt tokens + some for generation
        let batch_size = (tokens.len() + 512).max(1024);
        let mut batch = LlamaBatch::new(batch_size, 1);
        
        // Add tokens to batch
        for (i, token) in tokens.iter().enumerate() {
            // Mark last token as logits-generating
            let is_last = i == tokens.len() - 1;
            batch.add(*token, i as i32, &[0], is_last)
                .context("Failed to add token to batch")?;
        }
        
        // Decode (process the prompt)
        context.decode(&mut batch)
            .context("Failed to decode batch")?;
        
        println!("✅ Prompt decoded, starting generation...");
        
        // Generate response
        let mut output = String::new();
        let max_tokens = 512;
        let mut generated = 0;
        
        // Create a greedy sampler for deterministic token selection
        let mut sampler = LlamaSampler::greedy();
        
        while generated < max_tokens {
            // Sample next token using the sampler
            // idx -1 means use the last token in the context
            let new_token_id = sampler.sample(&context, -1);
            
            // Check for EOS
            if self.model.is_eog_token(new_token_id) {
                println!("🏁 Reached end of generation");
                break;
            }
            
            // Convert token to text
            if let Ok(piece) = self.model.token_to_str(new_token_id, Special::Tokenize) {
                output.push_str(&piece);
            }
            
            // Progress logging every 50 tokens
            if generated % 50 == 0 {
                println!("⏳ Generated {}/{} tokens...", generated, max_tokens);
            }
            
            // Add token to context for next iteration
            batch.clear();
            batch.add(new_token_id, generated as i32 + tokens.len() as i32, &[0], true)
                .context("Failed to add generated token")?;
            
            context.decode(&mut batch)
                .context("Failed to decode generated token")?;
            
            generated += 1;
        }
        
        println!("✅ Generated {} tokens ({} chars)", generated, output.len());
        Ok(output.trim().to_string())
    }
    
    pub fn is_ready(&self) -> bool {
        true // If we got here, model is loaded
    }
}
