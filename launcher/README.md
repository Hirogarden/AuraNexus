# AuraNexus Launcher

Self-updating launcher for AuraNexus with Docker management.

## Features

- ✅ **Auto-update checking** - Checks for launcher and image updates on startup
- ✅ **Self-updating** - Launcher can update itself automatically
- ✅ **Docker management** - Starts/stops/restarts Docker Compose services
- ✅ **System tray integration** - Minimize to tray with status menu
- ✅ **Health checks** - Waits for services to be ready before launching UI
- ✅ **Configurable** - Settings stored in `%LOCALAPPDATA%\AuraNexus\launcher_config.json`

## Development

### Running from Source

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install PySide6 requests

# Run launcher
python launcher\launcher.py
```

### Building Executable

```powershell
# Build launcher.exe
.\build_launcher.ps1

# Output: dist\AuraNexusLauncher.exe
```

### Building with Custom Icon

```powershell
# Create icon at assets\icon.ico
.\build_launcher.ps1 -Icon "assets\icon.ico"
```

## Configuration

Configuration file: `%LOCALAPPDATA%\AuraNexus\launcher_config.json`

```json
{
  "updates": {
    "check_on_startup": true,
    "auto_install_launcher": true,
    "auto_install_images": false,
    "channel": "stable"
  },
  "launcher": {
    "auto_launch_ui": true,
    "minimize_to_tray": true
  }
}
```

## Update Flow

1. **Launcher starts** → Check GitHub for new launcher version
2. **If new launcher** → Download, replace self, restart
3. **Check Docker** → Install if missing
4. **Check images** → Pull updates if configured
5. **Start services** → Run `docker-compose up -d`
6. **Health check** → Wait for http://localhost:8000/health
7. **Launch UI** → Open browser and minimize to tray

## System Tray Menu

Right-click tray icon:
- ✓ Running (status)
- Open Web UI
- View Logs
- Check for Updates
- Restart Services
- Stop Services
- Settings
- About
- Quit

## Distribution

For end users, distribute:
1. `AuraNexusLauncher.exe` (single file)
2. `docker-compose.yml` (in same directory)
3. Optional: Character configs in `data/characters/`

Users just need to:
1. Download `AuraNexusLauncher.exe`
2. Double-click to run
3. Launcher handles everything else!

## Architecture

```
AuraNexusLauncher.exe
├── launcher.py          # Main GUI
├── updater.py           # Update checking logic
├── docker_manager.py    # Docker Compose wrapper
└── config.py            # Configuration management
```

## Future Enhancements

- [ ] Docker Desktop auto-install
- [ ] Settings dialog UI
- [ ] Log viewer window
- [ ] Beta/Nightly update channels
- [ ] Rollback to previous version
- [ ] Offline mode detection
- [ ] Custom update server
