# AuraNexus — Developer Quickstart

This document provides packaged dev setup instructions for Windows and macOS/Linux. The repository includes helper scripts to automate checks and installs.

Windows (PowerShell)

1. Open PowerShell as Administrator (only required if installing system packages).
2. Run the prereq check script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_prereqs.ps1
```

3. Run the packaged dev setup (creates a Python venv and installs deps, runs `npm install` for the UI):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev_setup.ps1
```

4. Start the backend services (in one terminal):

```powershell
cmd /c "app\.venv\Scripts\activate && python app\aura_launcher.py start-all"
```

5. Start the Electron UI (in another terminal):

```powershell
cd ui\electron
npm run start
```

macOS / Linux (bash)

1. Ensure `node`, `npm`, `python3` and `pip` are on your PATH.
2. Run the packaged setup script:

```bash
./scripts/dev_setup.sh
```

3. Start the backend services:

```bash
source app/.venv/bin/activate
python app/aura_launcher.py start-all
```

4. Start the Electron UI:

```bash
cd ui/electron
npm run start
```

Notes
- The `ui/electron/scripts/check_prereqs.js` script is used by the setup helpers; it will exit non-zero if required tools are missing.
- If PowerShell blocks `Activate.ps1`, use the `-ExecutionPolicy Bypass` shown above or run the commands in a Command Prompt.
- These scripts are intended for developer convenience; CI and packaging scripts may differ for release builds.
