# KoboldCPP Integration Guide

## Quick Start

### 1. Get a Model

Download a GGUF model (recommended for storytelling):
- **Small (2-4GB)**: Phi-2, TinyLlama, Mistral-7B-Instruct (Q4)
- **Medium (8-12GB)**: Mistral-7B-Instruct (Q6), Llama-2-13B (Q4)
- **Large (20GB+)**: Llama-2-70B (Q4), Mixtral-8x7B (Q4)

Sources:
- https://huggingface.co/TheBloke (many GGUF models)
- https://huggingface.co/bartowski (newer models)

Example download:
```bash
# Mistral-7B-Instruct (good for storytelling, ~4GB)
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

### 2. Start KoboldCPP

From the `Repos/1-LLM-Inference/koboldcpp` directory:

**CPU Only:**
```bash
python koboldcpp.py --model /path/to/your/model.gguf --port 5001 --contextsize 4096
```

**With GPU (CUDA):**
```bash
python koboldcpp.py --model /path/to/your/model.gguf --port 5001 --contextsize 4096 --gpulayers 35
```

**With GPU (Vulkan - AMD/Intel):**
```bash
python koboldcpp.py --model /path/to/your/model.gguf --port 5001 --contextsize 4096 --usevulkan --gpulayers 35
```

**Quick test (using llama.cpp from repos):**
```bash
cd C:\Users\hirog\Repos\9-Utilities\llama.cpp
# Build first if not done: cmake -B build && cmake --build build --config Release
.\build\bin\Release\server.exe -m /path/to/model.gguf -c 4096 --host 127.0.0.1 --port 5001
```

### 3. Verify KoboldCPP is Running

Open browser to: http://localhost:5001

Or test with curl:
```bash
curl http://localhost:5001/api/v1/model
```

### 4. Test AuraNexus Integration

```bash
cd C:\Users\hirog\All-In-One\AuraNexus\electron-app
python test_llm_integration.py
```

Should show:
```
✅ KoboldCPP is running
   Model: your-model-name
```

### 5. Start AuraNexus Backend with LLM

```bash
cd C:\Users\hirog\All-In-One\AuraNexus\electron-app\backend
python core_app.py --port 8001
```

All agents will now use KoboldCPP for responses!

## Configuration

### Environment Variables

```bash
# Change KoboldCPP URL (default: http://127.0.0.1:5001)
set KCPP_URL=http://localhost:5001

# For remote KoboldCPP instance
set KCPP_URL=http://192.168.1.100:5001
```

### Agent Configuration

Edit `agent_manager_async.py` to adjust per-agent settings:

```python
"narrator": {
    "role": "narrator",
    "personality": "descriptive, immersive",
    "use_llm": True,           # Enable/disable LLM for this agent
    "temperature": 0.8,        # Creativity (0.0-2.0, higher = more creative)
    "max_tokens": 250          # Max response length
}
```

### LLM Parameters

- **temperature**: Controls randomness (0.1 = focused, 1.0 = balanced, 1.5+ = very creative)
- **max_tokens**: Maximum response length (150-500 recommended)
- **top_p**: Nucleus sampling (0.9 default, lower = more focused)
- **top_k**: Top-K sampling (40 default)
- **rep_pen**: Repetition penalty (1.1 default, higher = less repetition)

## Troubleshooting

### "Cannot connect to KoboldCPP"
- Make sure KoboldCPP is running on port 5001
- Check firewall settings
- Verify with: `curl http://localhost:5001/api/v1/model`

### "KoboldCPP returns empty response"
- Model might be too small for the prompt
- Try increasing context size: `--contextsize 8192`
- Reduce max_tokens in agent config

### "LLM responses are slow"
- Use GPU acceleration (`--gpulayers 35` or more)
- Use a smaller/quantized model (Q4 or Q5)
- Reduce context size if not needed

### "Responses are incoherent"
- Lower the temperature (try 0.6-0.7)
- Use a better model (Mistral, Llama2)
- Adjust system prompts in `async_agent.py`

## Fallback Mode

If KoboldCPP is unavailable, agents automatically fall back to rule-based responses:
- Narrator: Descriptive storytelling
- Characters: Personality-based reactions
- Director: Scene guidance

Disable LLM per-agent:
```python
"agent_name": {
    "use_llm": False,  # Use fallback rules instead
    # ...
}
```

## API Endpoints

The backend now supports LLM-powered responses:

```bash
# Send to specific agent
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "A dragon appears!", "target_agent": "narrator"}'

# Broadcast to all agents
curl -X POST http://localhost:8001/broadcast \
  -H "Content-Type: application/json" \
  -d '{"message": "The adventure begins!"}'
```

## Next Steps

1. **Test with a real model** - Download and start KoboldCPP
2. **Tune agent personalities** - Adjust system prompts and temperatures
3. **Add memory (Option C)** - Integrate Mem0 for persistent context
4. **Custom stop sequences** - Fine-tune generation stopping
5. **Streaming responses** - Add SSE for real-time generation
