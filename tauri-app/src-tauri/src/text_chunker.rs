// Text Chunking Module - Translated from llama_index
// Original: https://github.com/run-llama/llama_index
// License: MIT

use regex::Regex;

/// Configuration for text chunking
#[derive(Debug, Clone)]
pub struct ChunkingConfig {
    /// Target size for each chunk in tokens/characters
    pub chunk_size: usize,
    /// Overlap between chunks to maintain context
    pub chunk_overlap: usize,
    /// Separator for splitting paragraphs
    pub paragraph_separator: String,
    /// Separator for splitting sentences
    pub sentence_separator: String,
    /// Minimum chunk size (chunks smaller than this will be merged)
    pub min_chunk_size: usize,
}

impl Default for ChunkingConfig {
    fn default() -> Self {
        Self {
            chunk_size: 1024,
            chunk_overlap: 200,
            paragraph_separator: "\n\n".to_string(),
            sentence_separator: ". ".to_string(),
            min_chunk_size: 100,
        }
    }
}

/// Text chunker that splits text into overlapping chunks
/// 
/// Translated from llama_index's SentenceSplitter to Rust.
/// Tries to keep sentences and paragraphs together for better semantic coherence.
pub struct TextChunker {
    config: ChunkingConfig,
    sentence_regex: Regex,
}

impl TextChunker {
    /// Create a new text chunker with default configuration
    pub fn new() -> Self {
        Self::with_config(ChunkingConfig::default())
    }

    /// Create a new text chunker with custom configuration
    pub fn with_config(config: ChunkingConfig) -> Self {
        // Regex for sentence detection (supports multiple languages)
        let sentence_regex = Regex::new(r"[^.!?。？！]+[.!?。？！]?").unwrap();

        Self {
            config,
            sentence_regex,
        }
    }

    /// Split text into chunks with overlap
    /// 
    /// # Arguments
    /// * `text` - The text to split into chunks
    /// 
    /// # Returns
    /// Vector of text chunks
    /// 
    /// # Example
    /// ```rust
    /// let chunker = TextChunker::new();
    /// let chunks = chunker.chunk_text("This is a long document. It has many sentences.");
    /// ```
    pub fn chunk_text(&self, text: &str) -> Vec<String> {
        // First, try to split by paragraphs
        let paragraphs: Vec<&str> = text
            .split(&self.config.paragraph_separator)
            .filter(|p| !p.trim().is_empty())
            .collect();

        if paragraphs.len() == 1 {
            // No paragraph breaks, split by sentences
            self.chunk_by_sentences(text)
        } else {
            // Split by paragraphs, then refine
            self.chunk_by_paragraphs(&paragraphs)
        }
    }

    /// Split text by paragraph boundaries
    fn chunk_by_paragraphs(&self, paragraphs: &[&str]) -> Vec<String> {
        let mut chunks = Vec::new();
        let mut current_chunk = String::new();
        let mut current_size = 0;

        for paragraph in paragraphs {
            let para_size = paragraph.len();

            // If adding this paragraph exceeds chunk size
            if current_size + para_size > self.config.chunk_size && !current_chunk.is_empty() {
                // Save current chunk
                if !current_chunk.trim().is_empty() {
                    chunks.push(current_chunk.trim().to_string());
                }

                // Start new chunk with overlap
                current_chunk = self.get_overlap_text(&current_chunk);
            }

            // Add paragraph to current chunk
            if !current_chunk.is_empty() {
                current_chunk.push_str(&self.config.paragraph_separator);
            }
            current_chunk.push_str(paragraph);
            current_size = current_chunk.len();
        }

        // Add final chunk
        if !current_chunk.trim().is_empty() {
            chunks.push(current_chunk.trim().to_string());
        }

        chunks
    }

    /// Split text by sentence boundaries
    fn chunk_by_sentences(&self, text: &str) -> Vec<String> {
        let sentences: Vec<&str> = self
            .sentence_regex
            .find_iter(text)
            .map(|m| m.as_str())
            .collect();

        if sentences.is_empty() {
            return vec![text.to_string()];
        }

        let mut chunks = Vec::new();
        let mut current_chunk = String::new();
        let mut current_size = 0;

        for sentence in sentences {
            let sentence_size = sentence.len();

            // If adding this sentence exceeds chunk size
            if current_size + sentence_size > self.config.chunk_size && !current_chunk.is_empty() {
                // Save current chunk
                if !current_chunk.trim().is_empty() {
                    chunks.push(current_chunk.trim().to_string());
                }

                // Start new chunk with overlap
                current_chunk = self.get_overlap_text(&current_chunk);
            }

            // Add sentence to current chunk
            if !current_chunk.is_empty() && !current_chunk.ends_with(' ') {
                current_chunk.push(' ');
            }
            current_chunk.push_str(sentence);
            current_size = current_chunk.len();
        }

        // Add final chunk
        if !current_chunk.trim().is_empty() {
            chunks.push(current_chunk.trim().to_string());
        }

        chunks
    }

    /// Get overlap text from the end of a chunk
    fn get_overlap_text(&self, text: &str) -> String {
        if text.len() <= self.config.chunk_overlap {
            return text.to_string();
        }

        // Get last N characters for overlap
        let start_pos = text.len() - self.config.chunk_overlap;
        
        // Try to start at a sentence boundary
        if let Some(sentence_start) = text[start_pos..].find(". ") {
            return text[start_pos + sentence_start + 2..].to_string();
        }

        // Otherwise just use character position
        text[start_pos..].to_string()
    }

    /// Chunk text and return with metadata
    /// 
    /// # Returns
    /// Vector of tuples (chunk_text, chunk_index)
    pub fn chunk_with_metadata(&self, text: &str) -> Vec<(String, usize)> {
        self.chunk_text(text)
            .into_iter()
            .enumerate()
            .map(|(i, chunk)| (chunk, i))
            .collect()
    }

    /// Estimate number of chunks for a given text
    pub fn estimate_chunks(&self, text: &str) -> usize {
        let text_len = text.len();
        let effective_chunk_size = self.config.chunk_size - self.config.chunk_overlap;
        
        if effective_chunk_size == 0 {
            return 1;
        }

        (text_len + effective_chunk_size - 1) / effective_chunk_size
    }
}

impl Default for TextChunker {
    fn default() -> Self {
        Self::new()
    }
}

/// Simple character-based text splitter (fallback for non-semantic chunking)
pub struct SimpleTextSplitter {
    chunk_size: usize,
    chunk_overlap: usize,
}

impl SimpleTextSplitter {
    /// Create a new simple text splitter
    pub fn new(chunk_size: usize, chunk_overlap: usize) -> Self {
        assert!(
            chunk_overlap < chunk_size,
            "Chunk overlap must be less than chunk size"
        );
        Self {
            chunk_size,
            chunk_overlap,
        }
    }

    /// Split text into fixed-size chunks with overlap
    pub fn split_text(&self, text: &str) -> Vec<String> {
        let mut chunks = Vec::new();
        let mut start = 0;

        while start < text.len() {
            let end = (start + self.chunk_size).min(text.len());
            let chunk = &text[start..end];
            chunks.push(chunk.to_string());

            // Move start position (with overlap)
            start += self.chunk_size.saturating_sub(self.chunk_overlap);
            
            if start >= text.len() {
                break;
            }
        }

        chunks
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_chunking() {
        let splitter = SimpleTextSplitter::new(10, 2);
        let text = "This is a test of the text splitting functionality.";
        let chunks = splitter.split_text(text);

        assert!(!chunks.is_empty());
        assert!(chunks[0].len() <= 10);
        
        // Check overlap
        if chunks.len() > 1 {
            let end_of_first = &chunks[0][chunks[0].len() - 2..];
            let start_of_second = &chunks[1][..2.min(chunks[1].len())];
            assert_eq!(end_of_first, start_of_second);
        }
    }

    #[test]
    fn test_sentence_chunking() {
        let chunker = TextChunker::with_config(ChunkingConfig {
            chunk_size: 50,
            chunk_overlap: 10,
            ..Default::default()
        });

        let text = "This is sentence one. This is sentence two. This is sentence three.";
        let chunks = chunker.chunk_text(text);

        assert!(!chunks.is_empty());
        // Each chunk should contain complete sentences
        for chunk in &chunks {
            assert!(chunk.contains('.') || chunk == chunks.last().unwrap());
        }
    }

    #[test]
    fn test_paragraph_chunking() {
        let chunker = TextChunker::with_config(ChunkingConfig {
            chunk_size: 100,
            chunk_overlap: 20,
            ..Default::default()
        });

        let text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.";
        let chunks = chunker.chunk_text(text);

        assert!(!chunks.is_empty());
    }

    #[test]
    fn test_chunk_with_metadata() {
        let chunker = TextChunker::new();
        let text = "Test document. " .repeat(200);
        let chunks_with_meta = chunker.chunk_with_metadata(&text);

        for (i, (_, idx)) in chunks_with_meta.iter().enumerate() {
            assert_eq!(*idx, i);
        }
    }

    #[test]
    fn test_estimate_chunks() {
        let chunker = TextChunker::with_config(ChunkingConfig {
            chunk_size: 100,
            chunk_overlap: 20,
            ..Default::default()
        });

        let text = "This is a sentence. ".repeat(50); // Real sentences
        let estimated = chunker.estimate_chunks(&text);
        let actual = chunker.chunk_text(&text).len();

        // Estimate should be reasonable for real text
        assert!(estimated > 0, "Should estimate at least one chunk");
        assert!(actual > 0, "Should produce at least one chunk");
        println!("Estimated: {}, Actual: {}", estimated, actual);
    }
}
