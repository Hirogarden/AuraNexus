# Quick Start Guide - AuraNexus Launcher

## ✨ What You Just Created

A **self-updating launcher** that:
- Checks for updates automatically on startup
- Manages Docker containers behind the scenes  
- Provides system tray integration
- Gives users a simple "double-click to run" experience

## 📁 Files Created

```
AuraNexus/
├── launcher/
│   ├── launcher.py          # Main GUI application
│   ├── updater.py           # Auto-update logic
│   ├── docker_manager.py    # Docker Compose wrapper
│   ├── config.py            # Settings management
│   └── README.md            # Detailed documentation
└── build_launcher.ps1       # Build script for .exe
```

## 🚀 Try It Now

### Option 1: Run from Source
```powershell
# Make sure you're in the AuraNexus directory
cd C:\Users\hirog\All-In-One\AuraNexus

# Activate virtual environment (if not already)
.\.venv\Scripts\Activate.ps1

# Run the launcher
python launcher\launcher.py
```

### Option 2: Build Executable
```powershell
# Build the standalone .exe
.\build_launcher.ps1

# Run it
.\dist\AuraNexusLauncher.exe
```

## 🎯 What Happens When You Run It

1. **Window appears** with "🌟 AuraNexus" title
2. **Progress bar** shows update checking
3. **Status updates** show what's happening:
   - "Checking for launcher updates..."
   - "Checking Docker installation..."
   - "Checking for image updates..."
   - "Starting AuraNexus services..."
   - "Waiting for services to be ready..."
   - "✓ Ready to launch!"
4. **Browser opens** to http://localhost:8000
5. **Window minimizes** to system tray

## ⚙️ Configuration

Configuration file created at:
`%LOCALAPPDATA%\AuraNexus\launcher_config.json`

Default settings:
```json
{
  "updates": {
    "check_on_startup": true,           // Check on every launch
    "auto_install_launcher": true,      // Auto-update launcher
    "auto_install_images": false,       // Ask before updating images
    "channel": "stable"                 // stable | beta | nightly
  },
  "launcher": {
    "auto_launch_ui": true,             // Open browser automatically
    "minimize_to_tray": true            // Minimize after launch
  }
}
```

## 🎮 System Tray Features

Right-click the tray icon to:
- **Open Web UI** - Opens browser to localhost:8000
- **View Logs** - See what's happening
- **Check for Updates** - Manual update check
- **Restart Services** - Restart all containers
- **Stop Services** - Stop everything
- **Settings** - Configure launcher (coming soon)
- **Quit** - Stop services and exit

## 🔄 Update Flow Explained

### When User Launches:
```
1. Launcher starts
   ↓
2. Check GitHub for new launcher.exe
   → If available: Download → Replace → Restart
   ↓
3. Check if Docker installed
   → If not: Prompt to install
   ↓
4. Check Docker images for updates
   → Pull new versions (if auto-update enabled)
   ↓
5. Start docker-compose up -d
   ↓
6. Wait for health check (http://localhost:8000/health)
   ↓
7. Open browser → Minimize to tray
   ↓
8. User sees: "✓ Running" in tray
```

### Self-Update Process:
```
1. Launcher detects new version on GitHub
2. Downloads AuraNexusLauncher.exe (new version)
3. Saves as AuraNexusLauncher.exe.new
4. Creates update_launcher.bat:
   - Wait 2 seconds
   - Replace old .exe with new
   - Start new .exe
   - Delete update script
5. Exits current launcher
6. Batch script runs
7. New launcher starts
8. User sees: "Updated to v1.1.0" message
```

## 📦 Distribution

### For End Users:

**Single File Distribution:**
```
Just send them: AuraNexusLauncher.exe
(Everything else is downloaded automatically)
```

**Complete Package:**
```
AuraNexusRelease/
├── AuraNexusLauncher.exe    # Launcher
├── docker-compose.yml        # Service definitions
└── data/                     # Optional: Pre-configured characters
    └── characters/
        ├── fighter.yaml
        ├── wizard.yaml
        └── cleric.yaml
```

Users just:
1. Download folder
2. Double-click `AuraNexusLauncher.exe`
3. Wait for setup
4. Start chatting!

## 🔧 Customization

### Change Update Channel:
```json
// In launcher_config.json
"updates": {
  "channel": "beta"  // Get pre-release versions
}
```

### Disable Auto-Updates:
```json
"updates": {
  "check_on_startup": false,
  "auto_install_launcher": false
}
```

### Custom GitHub Repo:
```python
# In launcher/updater.py, line 20:
self.github_repo = "yourusername/auranexus"
```

## 🎨 Adding a Custom Icon

1. Create icon file: `assets/icon.ico`
2. Build with icon:
   ```powershell
   .\build_launcher.ps1 -Icon "assets\icon.ico"
   ```

## 🐛 Troubleshooting

### "Docker not found"
- Launcher will prompt to install Docker Desktop
- Manual: Download from docker.com

### "Services failed to start"
- Check if ports are in use (11434, 8000)
- View logs: Right-click tray → View Logs

### "Update check failed"
- Check internet connection
- GitHub API rate limits (60 req/hour unauthenticated)

## 📚 Next Steps

1. **Test the launcher** - Run it and see the UI
2. **Build the .exe** - Use `build_launcher.ps1`
3. **Test updates** - Create a GitHub release and test auto-update
4. **Add your icon** - Make it look professional
5. **Deploy!** - Share with users

## 💡 Pro Tips

**For Development:**
- Keep launcher running while developing
- It auto-restarts services on crash
- System tray shows status

**For Production:**
- Tag releases: v1.0.0, v1.1.0, etc.
- Include changelog in releases
- Test updates before pushing to stable

**For Users:**
- Create desktop shortcut to launcher.exe
- Pin to taskbar
- Enable "Start with Windows" (future feature)

## 🎉 You're Done!

You now have a professional auto-updating launcher that:
✅ Simplifies Docker complexity for users
✅ Handles updates automatically
✅ Provides great UX with system tray
✅ Manages all services behind the scenes

**The best of both worlds:** Simple .exe + Powerful Docker! 🚀
