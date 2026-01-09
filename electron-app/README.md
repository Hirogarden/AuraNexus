# AuraNexus Electron App

## Quick Start

1. Install dependencies:
   ```
   npm install
   ```

2. Run in development:
   ```
   npm start
   ```

3. Build executable:
   ```
   npm run build
   ```

## Architecture

- **Electron**: Window management, Python subprocess launcher
- **Python Backend**: FastAPI server with agent orchestration
- **Bundled Resources**: KoboldCPP, pre-downloaded models

## Model Bundling Strategy

Pre-package popular models in installer:
- Phi-3-mini (2.3GB) - Multilingual
- Mistral-7B-Instruct (4.1GB) - English default
- Qwen2-7B (4.4GB) - Chinese/Asian languages

User selects language during first run, extracts only needed model.

## Next Steps

1. Create Python backend in `backend/` folder
2. Build agent system (replaces Docker containers)
3. Configure electron-builder for packaging
4. Add model download/extraction logic
