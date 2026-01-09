# Bundled Ollama Architecture

AuraNexus now includes its own bundled version of Ollama, making it truly self-contained and portable.

## Directory Structure

```
AuraNexus/
├── engines/
│   └── ollama/
│       ├── bin/
│       │   └── ollama.exe          # Bundled Ollama executable
│       └── models/                  # Bundled Ollama models (isolated)
│           ├── manifests/
│           └── blobs/
└── src/
    ├── ollama_bundle_manager.py    # Manages bundled installation
    └── ollama_service_manager.py   # Starts bundled or system Ollama
```

## How It Works

1. **First Launch**: When AuraNexus starts for the first time:
   - Checks if bundled Ollama exists in `engines/ollama/bin/`
   - If not found, automatically downloads Ollama from official releases
   - Extracts to the bundled directory
   - Sets up isolated model storage

2. **Environment Isolation**:
   - Sets `OLLAMA_MODELS` to `engines/ollama/models/`
   - Sets `OLLAMA_HOST` to `127.0.0.1:11434`
   - Runs on localhost only (secure by default)
   - Does NOT interfere with system-wide Ollama installations

3. **Startup**:
   - Bundled Ollama starts automatically with AuraNexus
   - Uses isolated model directory
   - API accessible at `http://localhost:11434`

## Benefits

✅ **Fully Portable**: Copy the AuraNexus folder anywhere and it works
✅ **No System Dependencies**: No need to install Ollama separately
✅ **Isolated**: Doesn't conflict with system Ollama installations
✅ **Self-Updating**: Can manage its own Ollama version independently
✅ **Model Management**: Models stored within AuraNexus directory

## Model Storage

Models are stored in `engines/ollama/models/` instead of the system default:
- **Windows System**: `C:\Users\<username>\.ollama\models`
- **AuraNexus Bundled**: `<AuraNexus>\engines\ollama\models`

This means:
- Models don't clutter your user profile
- Easy to backup/move the entire AuraNexus folder
- Can use different model sets for different projects

## Switching Between Bundled and System Ollama

In `chat_launcher.py`:

```python
# Use bundled Ollama (default)
manager = OllamaServiceManager(use_bundled=True)

# Use system Ollama instead
manager = OllamaServiceManager(use_bundled=False)
```

## Sharing Models with System Ollama

If you want to share models between system and bundled installations:

**Option 1: Set environment variable**
```powershell
$env:OLLAMA_MODELS = "C:\Users\YourName\.ollama\models"
python chat_launcher.py
```

**Option 2: Copy models manually**
```powershell
# Copy from system to bundled
Copy-Item -Recurse "$env:USERPROFILE\.ollama\models\*" "engines\ollama\models\"

# Or create symlink (requires admin)
New-Item -ItemType SymbolicLink -Path "engines\ollama\models" -Target "$env:USERPROFILE\.ollama\models"
```

## Manual Download

If auto-download fails, manually download Ollama:

1. Download from: https://ollama.com/download
2. Extract `ollama.exe` to `engines/ollama/bin/`
3. Restart AuraNexus

## Troubleshooting

**"Failed to download Ollama"**
- Check internet connection
- Verify firewall allows downloads from github.com
- Manually download and place in `engines/ollama/bin/`

**"Could not connect to Ollama"**
- Wait 5-10 seconds for Ollama to fully start
- Check if port 11434 is available (not used by another process)
- Check `engines/ollama/bin/ollama.exe` exists

**Models not showing up**
- Check `engines/ollama/models/` directory
- Pull models using: `engines\ollama\bin\ollama.exe pull llama3.2`
- Or use the 📥 download button in the UI

## File Sizes

- **Ollama executable**: ~200-500 MB (depending on platform)
- **Models**: Varies (typically 2-8 GB each)
- **Total for basic setup**: ~5-10 GB

## Performance

Bundled Ollama runs with identical performance to system-installed Ollama. The only difference is file locations.
