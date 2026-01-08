#!/usr/bin/env python3
"""
AuraNexus - Unified Application Launcher
Run this file to start AuraNexus

RECOMMENDED: Use run_aura_nexus.ps1 instead (handles venv automatically)
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    # Import and launch the simple chat launcher
    print("Launching AuraNexus Chat...")
    
    # Import the chat launcher
    import subprocess
    app_path = Path(__file__).parent / "chat_launcher.py"
    
    # Run the chat app
    sys.exit(subprocess.call([sys.executable, str(app_path)]))
    
    # Import and run main
    from main import main
    sys.exit(main())

