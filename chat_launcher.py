#!/usr/bin/env python3
"""AuraNexus Simple Chat Launcher - Main Entry Point

This launches the simple Ollama chat window with all upgraded features.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication
from ollama_chat import OllamaChatWindow

def main():
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("AuraNexus")
    app.setApplicationDisplayName("AuraNexus Chat")
    app.setOrganizationName("AuraNexus")
    
    # Create and show chat window
    window = OllamaChatWindow(project_name="Chat")
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
