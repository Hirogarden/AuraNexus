# Quick Start Testing Guide

## Prerequisites

1. **Install Dependencies**:
   ```powershell
   cd electron-app\backend
   pip install -r requirements.txt
   ```

2. **Get a Model**:
   - Download a GGUF model (Mistral-7B, Llama-2-7B, etc.)
   - Place in `electron-app\backend\models\` directory
   - Or set environment variable: `$env:MODEL_PATH="C:\path\to\model.gguf"`

## Test 1: Start Backend

```powershell
cd electron-app\backend
python core_app.py --port 8000
```

**Expected Output**:
```
Starting AuraNexus backend...
Attempting auto-load of model...
✅ Model loaded IN-PROCESS (secure, HIPAA-compliant)
   Path: ./models/your-model.gguf
   Context: 4096
   Size: 4.37 GB
Backend ready - async agents running!
```

## Test 2: Basic Chat

**PowerShell**:
```powershell
$body = @{
    message = "Tell me a short story about a dragon"
    target_agent = "narrator"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

**Expected**:
- Response from narrator agent
- No repetitive phrases
- Creative and varied (XTC + DRY sampling)

## Test 3: Memory System

### Check Memory Stats
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/memory/stats"
```

**Expected**:
```json
{
  "short_term_messages": 2,
  "max_history": 20,
  "rag_enabled": true,
  "long_term_documents": 0
}
```

### Send Multiple Messages
```powershell
# Send 25 messages to trigger archival
for ($i=1; $i -le 25; $i++) {
    $body = @{
        message = "Message $i about dragons and magic"
        target_agent = "narrator"
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "http://localhost:8000/chat" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
        
    Write-Host "Sent message $i"
    Start-Sleep -Milliseconds 500
}
```

### Query Memory (RAG)
```powershell
$query = @{
    query = "dragon"
    n_results = 3
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/memory/query" `
    -Method POST `
    -ContentType "application/json" `
    -Body $query
```

**Expected**:
- Returns 3 relevant memories about dragons
- Includes metadata (timestamp, distance)

### Check Stats Again
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/memory/stats"
```

**Expected**:
```json
{
  "short_term_messages": 20,
  "max_history": 20,
  "rag_enabled": true,
  "long_term_documents": 1
}
```
Note: `long_term_documents` increased (old messages archived)

## Test 4: Save/Load Conversation

### Save
```powershell
$save = @{
    filepath = "test_conversation.json"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/memory/save" `
    -Method POST `
    -ContentType "application/json" `
    -Body $save
```

**Check File**:
```powershell
Get-Content test_conversation.json | ConvertFrom-Json
```

### Clear Memory
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/memory/clear/short" `
    -Method POST
```

### Load Back
```powershell
$load = @{
    filepath = "test_conversation.json"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/memory/load" `
    -Method POST `
    -ContentType "application/json" `
    -Body $load
```

### Verify
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/memory/recent?n=5"
```

**Expected**: Previous conversation restored

## Test 5: Advanced Sampling

### Storytelling (High Creativity)
```powershell
$story = @{
    message = "Continue the epic tale of the wandering knight"
    target_agent = "narrator"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Body $story
```

**Observe**:
- High creativity (temp=0.9)
- No repetition (DRY=0.8)
- Varied word choices (XTC=0.1)

### Character Dialogue
```powershell
$dialogue = @{
    message = "What do you think about this quest?"
    target_agent = "character_1"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Body $dialogue
```

**Observe**:
- In-character response
- Uses storytelling preset
- Creative but coherent

## Test 6: Model Management

### Check Model Status
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/model"
```

**Expected**:
```json
{
  "loaded": true,
  "model_path": "./models/your-model.gguf",
  "context_size": 4096,
  "model_size_gb": 4.37,
  "gpu_layers": 35
}
```

## Test 7: Agent Management

### List Agents
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/agents"
```

**Expected**:
```json
{
  "agents": ["character_1", "character_2", "character_3", "narrator"],
  "running": ["character_1", "character_2", "character_3", "narrator"]
}
```

### Stop an Agent
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/agents/character_1/stop" `
    -Method POST
```

### Start an Agent
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/agents/character_1/start" `
    -Method POST
```

## Success Criteria

✅ **Backend starts without errors**  
✅ **Model loads successfully**  
✅ **Chat responses are coherent and non-repetitive**  
✅ **Memory archives after 20+ messages**  
✅ **RAG query retrieves relevant context**  
✅ **Save/load preserves conversation**  
✅ **Agents use role-specific sampling presets**

## Common Issues

### "No model loaded"
- Check `models/` directory has .gguf file
- Or set `MODEL_PATH` environment variable
- Backend will use fallback responses without model

### "ChromaDB not available"
- Run: `pip install chromadb sentence-transformers`
- Memory will work without RAG (short-term only)

### "GPU not detected"
- Install PyTorch with CUDA support
- Model will run on CPU (slower but functional)

### Port already in use
- Change port: `python core_app.py --port 8001`
- Or kill process using port 8000

## Next Steps

After successful testing:
1. Compare text quality with ChatGPT 3.5
2. Test 50+ message conversations for repetition
3. Benchmark storytelling against AI Dungeon
4. Tune sampling presets based on results
5. Build frontend UI for easier interaction

---

**Need Help?**
- Check logs in terminal
- See [PHASE1_IMPLEMENTATION_COMPLETE.md](PHASE1_IMPLEMENTATION_COMPLETE.md)
- Review [CORE_FOCUS.md](CORE_FOCUS.md)
