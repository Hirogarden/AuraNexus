#!/usr/bin/env python3
"""AuraNexus Secure Chat Launcher - Main Entry Point

This launches the secure chat window with integrated in-process inference.
No external services required - everything runs securely within the application.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox
from unified_chat_window import UnifiedChatWindow

def main():
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("AuraNexus")
    app.setApplicationDisplayName("AuraNexus - Unified Chat")
    app.setOrganizationName("AuraNexus")
    
    # Note: No external services to start - everything runs in-process!
    # The SecureInferenceEngine loads models directly when needed.
    
    print("Starting AuraNexus Unified Chat...")
    print("Using in-process inference (no external services)")
    print("Modes: AI Chatbot, Storyteller, AI Assistant")
    
    # Create and show unified chat window
    try:
        window = UnifiedChatWindow()
        window.show()
    except Exception as e:
        print(f"Error creating chat window: {e}")
        import traceback
        traceback.print_exc()
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to create chat window:\n{str(e)}"
        )
        return 1
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
