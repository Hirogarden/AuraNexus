# Model Setup Guide

## Using Existing Ollama Models

If you already have Ollama models downloaded elsewhere, you don't need to re-download them!

### Option 1: Set Ollama Models Directory (Recommended)

Before starting Ollama, set the `OLLAMA_MODELS` environment variable to point to your existing models:

**Windows PowerShell:**
```powershell
$env:OLLAMA_MODELS = "D:\YourModelsFolder"
ollama serve
```

**Windows (Permanent):**
1. Open System Properties → Environment Variables
2. Add new User/System variable:
   - Name: `OLLAMA_MODELS`
   - Value: `D:\YourModelsFolder` (your models path)
3. Restart Ollama

### Option 2: Copy/Move Existing Models

Copy your existing Ollama models to the default location:

**Default Ollama models location:**
- Windows: `C:\Users\YourName\.ollama\models`
- Linux: `~/.ollama/models`
- macOS: `~/.ollama/models`

**Model structure:**
```
.ollama/models/
├── manifests/
│   └── registry.ollama.ai/
│       └── library/
│           ├── llama3/
│           └── mistral/
└── blobs/
    ├── sha256-xxxxx...
    └── sha256-yyyyy...
```

### Option 3: Create Symlinks (Advanced)

Create symbolic links from the default location to your existing models:

**Windows (Run as Administrator):**
```powershell
# Stop Ollama first
Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue

# Create symlink to your models
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.ollama\models" -Target "D:\YourModelsFolder"

# Start Ollama
ollama serve
```

### Finding Your Existing Models

Check where your old Ollama installation stored models:

**Windows:**
```powershell
# Check environment variable
$env:OLLAMA_MODELS

# Common locations
ls "$env:USERPROFILE\.ollama\models"
ls "$env:LOCALAPPDATA\Ollama\models"
```

## Verifying Models Are Recognized

After setting up, verify Ollama can see your models:

```powershell
ollama list
```

You should see all your previously downloaded models!

## Downloading New Models

If you need new models:

**Via Terminal:**
```powershell
ollama pull llama3.2
ollama pull mistral
ollama pull codellama
```

**Via AuraNexus GUI:**
1. Click the 📥 (download) button in the model selector
2. Enter model name (e.g., `llama3.2`, `mistral`)
3. Wait for download to complete
4. Click 🔄 (refresh) to see the new model

## Popular Models

- **llama3.2** (7.9GB) - Fast, general-purpose
- **mistral** (7.2GB) - Strong reasoning
- **codellama** (3.8GB) - Code generation
- **phi3** (2.3GB) - Lightweight, good quality
- **gemma2** (5.4GB) - Google's latest

## Troubleshooting

**Models not showing up?**
1. Verify `OLLAMA_MODELS` variable is set correctly
2. Restart Ollama server: `Stop-Process -Name ollama; ollama serve`
3. Check folder structure matches Ollama's format
4. Run `ollama list` to see what Ollama recognizes

**Out of space?**
- Models can be 2-8GB each
- Store on a drive with plenty of space
- Use `OLLAMA_MODELS` to point to a larger drive
