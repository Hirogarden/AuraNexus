use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Information about a discovered model file
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    /// Full path to the model file
    pub path: String,
    /// Just the filename
    pub name: String,
    /// File size in bytes
    pub size: u64,
    /// Human-readable size (e.g., "4.2 GB")
    pub size_human: String,
    /// Last modified timestamp (Unix timestamp)
    pub modified: i64,
}

/// Scan for .gguf model files in the given directory and subdirectories
pub fn scan_models(models_dir: &Path) -> Result<Vec<ModelInfo>> {
    let mut models = Vec::new();

    if !models_dir.exists() {
        return Ok(models); // Return empty list if directory doesn't exist
    }

    for entry in WalkDir::new(models_dir)
        .follow_links(true)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();

        // Check if it's a .gguf file
        if let Some(extension) = path.extension() {
            if extension.eq_ignore_ascii_case("gguf") && path.is_file() {
                if let Ok(metadata) = std::fs::metadata(path) {
                    let size = metadata.len();
                    let modified = metadata
                        .modified()
                        .ok()
                        .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
                        .map(|duration| duration.as_secs() as i64)
                        .unwrap_or(0);

                    models.push(ModelInfo {
                        path: path.to_string_lossy().to_string(),
                        name: path
                            .file_name()
                            .unwrap_or_default()
                            .to_string_lossy()
                            .to_string(),
                        size,
                        size_human: format_size(size),
                        modified,
                    });
                }
            }
        }
    }

    // Sort by name
    models.sort_by(|a, b| a.name.cmp(&b.name));

    Ok(models)
}

/// Scan multiple directories for models
pub fn scan_all_model_locations() -> Result<Vec<ModelInfo>> {
    let mut all_models = Vec::new();

    // Common model locations
    let search_paths = vec![
        // Development: from src-tauri, go up to workspace root
        std::env::current_dir().ok().and_then(|p| Some(p.parent()?.parent()?.join("models"))),
        // Production: models next to exe
        std::env::current_exe().ok().and_then(|p| Some(p.parent()?.join("models"))),
        // Alternative: models in workspace root (when running from tauri-app/src-tauri/target/release)
        std::env::current_exe().ok().and_then(|p| {
            Some(p.parent()?.parent()?.parent()?.parent()?.parent()?.join("models"))
        }),
        // User's home directory models folder
        dirs::home_dir().map(|p| p.join("models")),
    ];

    for path_option in search_paths {
        if let Some(path) = path_option {
            if let Ok(models) = scan_models(&path) {
                // Add models, avoiding duplicates by path
                for model in models {
                    if !all_models.iter().any(|m: &ModelInfo| m.path == model.path) {
                        all_models.push(model);
                    }
                }
            }
        }
    }

    Ok(all_models)
}

/// Format byte size into human-readable string
fn format_size(bytes: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    
    if bytes == 0 {
        return "0 B".to_string();
    }

    let bytes_f = bytes as f64;
    let i = (bytes_f.log10() / 1024_f64.log10()).floor() as usize;
    let i = i.min(UNITS.len() - 1);
    
    let size = bytes_f / 1024_f64.powi(i as i32);
    
    format!("{:.2} {}", size, UNITS[i])
}

/// Tauri commands for model management
#[tauri::command]
pub async fn get_available_models() -> Result<Vec<ModelInfo>, String> {
    scan_all_model_locations().map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_model_info(model_path: String) -> Result<ModelInfo, String> {
    let path = Path::new(&model_path);
    
    if !path.exists() {
        return Err("Model file not found".to_string());
    }

    let metadata = std::fs::metadata(path)
        .map_err(|e| format!("Failed to read model metadata: {}", e))?;
    
    let size = metadata.len();
    let modified = metadata
        .modified()
        .ok()
        .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|duration| duration.as_secs() as i64)
        .unwrap_or(0);

    Ok(ModelInfo {
        path: model_path.clone(),
        name: path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string(),
        size,
        size_human: format_size(size),
        modified,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_size() {
        assert_eq!(format_size(0), "0 B");
        assert_eq!(format_size(1023), "1023.00 B");
        assert_eq!(format_size(1024), "1.00 KB");
        assert_eq!(format_size(1536), "1.50 KB");
        assert_eq!(format_size(1048576), "1.00 MB");
        assert_eq!(format_size(1073741824), "1.00 GB");
    }
}
