#!/usr/bin/env python3
"""
AuraNexus - Unified Application Launcher
Run this file to start AuraNexus
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Import and run main
from main import main

if __name__ == "__main__":
    sys.exit(main())
