# Embeddings & Memory Management

## Overview
AuraNexus now supports advanced Ollama features for embeddings and model memory management:

1. **Better Embedding API** - Efficient vector embeddings with batch support
2. **Model Memory Management** - View and control loaded models in RAM/VRAM

---

## 1. Embeddings (`/api/embed`)

Generate vector embeddings for semantic search, RAG, and similarity calculations.

### Features
- **Batch Processing**: Embed multiple texts in one request
- **Efficient**: Uses the modern `/api/embed` endpoint (not deprecated `/api/embeddings`)
- **Model Flexibility**: Use any Ollama model for embeddings

### Basic Usage

```python
from ollama_client import OllamaClient

client = OllamaClient(model="llama3.2")

# Single text
result = client.embed("Hello world")
embedding = result["embeddings"][0]  # List of floats
print(f"Dimensions: {len(embedding)}")  # e.g., 4096

# Batch processing
texts = ["First text", "Second text", "Third text"]
result = client.embed(texts)
embeddings = result["embeddings"]  # List of lists
print(f"Processed {len(embeddings)} texts")
```

### API Reference

```python
def embed(
    input: str | List[str],      # Text(s) to embed
    model: Optional[str] = None,  # Model override
    keep_alive: Optional[str] = None,  # Memory duration
    options: Optional[Dict] = None     # Model parameters
) -> Dict
```

**Returns:**
```python
{
    "model": "llama3.2:latest",
    "embeddings": [
        [0.123, -0.456, ...],  # First embedding
        [0.789, -0.012, ...]   # Second embedding (if batch)
    ]
}
```

### Use Cases

#### Semantic Search
```python
# Embed documents
docs = ["Python is a programming language", "Dogs are animals", "Cars have wheels"]
doc_embeddings = client.embed(docs)["embeddings"]

# Embed query
query = "programming"
query_embedding = client.embed(query)["embeddings"][0]

# Calculate similarity (cosine similarity)
import numpy as np

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

for i, doc in enumerate(docs):
    sim = cosine_similarity(query_embedding, doc_embeddings[i])
    print(f"{doc}: {sim:.3f}")
```

#### RAG Integration
```python
# Embed and store documents
texts = ["Document 1 content", "Document 2 content", ...]
embeddings = client.embed(texts)["embeddings"]

# Store in vector database (ChromaDB, Pinecone, etc.)
# ... storage code ...

# Query
query_vec = client.embed("user question")["embeddings"][0]
# Search vector database for similar documents
```

---

## 2. Model Memory Management

Control which models are loaded in RAM/VRAM to optimize resource usage.

### UI Features

The **Memory Management** section in the chat window provides:

1. **🔍 Show Loaded Models** - View all models currently in memory
   - Shows RAM and VRAM usage per model
   - Displays expiration times
   - Total memory consumption

2. **💾 Unload Current Model** - Free memory immediately
   - Removes model from RAM/VRAM
   - Useful for switching between large models

3. **Keep Alive** input - Control model lifetime
   - Examples: `5m` (5 minutes), `1h` (1 hour), `0` (immediate unload)
   - Set before sending messages

### API Reference

#### List Running Models
```python
result = client.list_running_models()

# Returns:
{
    "models": [
        {
            "name": "llama3.2:latest",
            "model": "llama3.2:latest",
            "size": 9216000000,      # Bytes
            "digest": "sha256:...",
            "expires_at": "2026-01-05T12:30:00Z",
            "size_vram": 7418000000  # VRAM usage in bytes
        }
    ]
}
```

#### Unload Model
```python
# Unload current model
success = client.unload_model()

# Unload specific model
success = client.unload_model("llama3.2:latest")
```

### Use Cases

#### Memory Optimization
```python
# Before loading a large model, unload others
client.list_running_models()  # Check what's loaded
client.unload_model("old-model:latest")  # Free memory

# Load new model (will auto-load on first use)
client.model = "large-model:70b"
response = client.chat([Message("user", "Hello")])
```

#### Long-Running Servers
```python
# Keep model loaded for 1 hour (reduce reload times)
result = client.embed("text", keep_alive="1h")

# Unload immediately after use (minimize memory)
result = client.embed("text", keep_alive="0")
```

#### Monitoring
```python
import time

while True:
    result = client.list_running_models()
    models = result.get("models", [])
    
    total_ram = sum(m["size"] for m in models) / (1024**3)  # GB
    total_vram = sum(m["size_vram"] for m in models) / (1024**3)
    
    print(f"RAM: {total_ram:.1f} GB | VRAM: {total_vram:.1f} GB")
    time.sleep(60)
```

---

## Integration with Existing Features

### Combined with Tool Calling
```python
# Enable tools with custom keep_alive
client.enable_tools()
response = client.chat(
    messages=[Message("user", "What time is it?")],
    tools=tools,
    keep_alive="10m"  # Keep model for 10 minutes
)
```

### Combined with Structured Outputs
```python
# Use embeddings to find relevant schema, then structure output
query_embedding = client.embed("user query")["embeddings"][0]
# ... find best schema from vector search ...

response = client.chat(
    messages=[Message("user", "Generate data")],
    format=selected_schema,
    keep_alive="5m"
)
```

---

## Best Practices

### Embeddings
1. **Batch when possible** - Much faster than individual requests
2. **Normalize vectors** - Use cosine similarity for comparison
3. **Cache results** - Embeddings are deterministic, store them
4. **Choose appropriate models** - Smaller models = faster, larger = better quality

### Memory Management
1. **Monitor usage** - Use "Show Loaded Models" to track memory
2. **Unload unused models** - Free RAM/VRAM between tasks
3. **Set appropriate keep_alive** - Balance speed vs memory
   - Frequent requests: `30m` or `1h`
   - Occasional use: `5m` or `0`
4. **Consider VRAM limits** - GPU memory is limited, unload when switching models

---

## Troubleshooting

### Embeddings

**Q: "Error: Model not found"**
- Model must be pulled first: `ollama pull llama3.2`
- Check available models in UI dropdown

**Q: "Different embedding dimensions"**
- Each model has fixed dimensions (e.g., llama3.2=4096)
- Don't mix embeddings from different models
- Re-embed everything if switching models

**Q: "Slow embedding performance"**
- Use batch processing instead of individual requests
- Consider using a dedicated embedding model (e.g., `nomic-embed-text`)

### Memory Management

**Q: "Model shows as loaded but using lots of memory"**
- Models stay in memory until `keep_alive` expires
- Manually unload with "Unload Current Model" button
- Or set `keep_alive="0"` in next request

**Q: "Out of VRAM error"**
- Check loaded models with "Show Loaded Models"
- Unload models you're not using
- Consider using smaller models or quantized versions

**Q: "Model reloads slowly after unloading"**
- First load is always slower (disk → memory)
- Use longer `keep_alive` if using model frequently
- SSD storage helps significantly

---

## Examples

See `test_memory_embed.py` for working examples:

```bash
python test_memory_embed.py
```

This demonstrates:
- Single and batch embeddings
- Listing loaded models
- Unloading models
- Memory monitoring
