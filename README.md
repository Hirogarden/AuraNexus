# AuraNexus

AuraNexus — unified local storytelling desktop app (scaffold).

This repo scaffolds an Electron desktop wrapper plus a Python "glue" layer to orchestrate:

- KoboldCPP (local LLM engine)  — submodule at `/engines/koboldcpp`
- SillyTavern (adventure frontend) — submodule at `/frontends/sillytavern`
- AnythingLLM (data manager / RAG) — submodule at `/data-manager/anything-llm`
- SillyTavern extensions (Extras, VRM) — placed under `/frontends/sillytavern/extensions`
- Piper TTS under `/tts/piper`

Quick start (development):

1. Initialize submodules (see `scripts/init_submodules.ps1`)
2. Create and activate a Python virtual environment, install Python deps, and start the launcher.

Windows (PowerShell) — temporary bypass for this session:

```powershell
cd AuraNexus
python -m venv .venv
# Allow activation for this session only (no permanent policy change)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\.venv\Scripts\Activate.ps1
pip install -r app/requirements.txt
python app/aura_launcher.py start-all
```

Windows (CMD alternative) — no policy changes required:

```cmd
cd AuraNexus
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r app/requirements.txt
python app/aura_launcher.py start-all
```

macOS / Linux:

```bash
cd AuraNexus
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
python app/aura_launcher.py start-all
```

3. In another terminal, start Electron UI:

```powershell
cd ui/electron
npm install
npm run start
```

Notes:
- This scaffold intentionally keeps upstream projects as submodules to preserve licensing and easy updates.
- You chose to keep AGPL components; when distributing, include source and installation info per AGPL.
