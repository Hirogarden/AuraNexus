# AuraNexus - Secure HIPAA-Compliant Installation

## Quick Start for Secure Mode

```powershell
# 1. Install inference engine (in-process, no external dependencies)
pip install llama-cpp-python

# 2. Download a model (one-time, can do offline later)
# Place GGUF model files in: engines/models/

# Example models (download from HuggingFace):
# - Phi-3-mini (3.8GB): https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf
# - Llama-3.2-3B (2GB): https://huggingface.co/lmstudio-community/Llama-3.2-3B-Instruct-GGUF
# - Mistral-7B (4.4GB): https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF

# 3. Run AuraNexus
python chat_launcher.py
```

## GPU Acceleration (Optional)

For NVIDIA GPUs:
```powershell
$env:CMAKE_ARGS = "-DLLAMA_CUBLAS=on"
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

For AMD GPUs:
```powershell
$env:CMAKE_ARGS = "-DLLAMA_HIPBLAS=on"
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

## Security Verification

After installation, verify no external dependencies:

```powershell
# Check imports in secure_inference_engine.py
Select-String -Path "src\secure_inference_engine.py" -Pattern "requests|urllib|socket|subprocess"
# Should return 0 matches

# Run with no network access
# Disable network adapter and verify AuraNexus still works (except model download)
```

## Directory Structure

```
AuraNexus/
├── engines/
│   └── models/           # Place your .gguf model files here
│       ├── phi-3-mini-4k-instruct-q4.gguf
│       ├── llama-3.2-3b-instruct-q4.gguf
│       └── mistral-7b-instruct-v0.2-q4.gguf
└── src/
    └── secure_inference_engine.py  # In-process inference (no external calls)
```

## Model Downloads

### Option 1: HuggingFace (Recommended)

Visit https://huggingface.co/models and search for "GGUF":
- Look for models with "Q4_K_M" or "Q5_K_M" quantization (good quality, reasonable size)
- Download to `engines/models/`

### Option 2: Air-Gapped Installation

On internet-connected machine:
```powershell
# Download model
curl -L -o phi-3.gguf "https://huggingface.co/..."

# Copy to USB drive
Copy-Item phi-3.gguf E:\models\
```

On secure machine:
```powershell
# Copy from USB
Copy-Item E:\models\phi-3.gguf engines\models\
```

## Performance Notes

**CPU Mode** (no GPU):
- Phi-3-mini: ~10-20 tokens/sec
- Llama-3.2-3B: ~5-15 tokens/sec
- Mistral-7B: ~3-10 tokens/sec

**GPU Mode** (with CUDA/ROCm):
- 10-50x faster depending on GPU
- Recommended for interactive chat

## Troubleshooting

**"No module named 'llama_cpp'"**
```powershell
pip install llama-cpp-python
```

**Slow inference on CPU**
```powershell
# Install with OpenBLAS acceleration
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

**Out of memory**
- Use smaller models (3B instead of 7B)
- Lower context size (n_ctx=2048 instead of 4096)
- Use Q4 quantization instead of Q5/Q6

## Next Steps

1. Install llama-cpp-python: `pip install llama-cpp-python`
2. Download a model to `engines/models/`
3. Run: `python chat_launcher.py`
4. Select model from dropdown
5. Start chatting (all processing stays local!)
