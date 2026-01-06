"""AuraNexus - OLD/DEPRECATED Launcher
THIS FILE IS DEPRECATED. Use aura_nexus_app.py instead.

This is an old project launcher from the previous program version.
Keeping for reference only - helpful code will be harvested later.

To run the current application, use:
    python aura_nexus_app.py
    OR
    run_aura_nexus.ps1
"""

import sys
print("=" * 60, file=sys.stderr)
print("DEPRECATED: This launcher is from the old program", file=sys.stderr)
print("Please use: python aura_nexus_app.py", file=sys.stderr)
print("=" * 60, file=sys.stderr)
sys.exit(1)

# ============================================================================
# OLD CODE BELOW - PRESERVED FOR REFERENCE ONLY
# ============================================================================

"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import Ollama-based chat window
from ollama_chat import OllamaChatWindow
"""


class ProjectLauncher(QMainWindow):
    """Main launcher window to select projects."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuraNexus - Project Launcher")
        self.setGeometry(100, 100, 600, 400)
        
        # Try to set icon
        try:
            icon_path = Path(__file__).parent.parent / "assets" / "aura_nexus.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the launcher UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("AuraNexus - Select Project")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Choose which AuraNexus configuration to run:\n\n"
            "Project A: Basic Assistant - Local LLM chat\n"
            "Project B: Interactive Storyteller - Chat with character interactions\n"
            "Project C: Full Companion - All features with avatar and image generation"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Buttons
        btn_a = QPushButton("Project A: Basic Assistant")
        btn_a.setMinimumHeight(50)
        btn_a.clicked.connect(self.launch_project_a)
        layout.addWidget(btn_a)
        
        btn_b = QPushButton("Project B: Interactive Storyteller")
        btn_b.setMinimumHeight(50)
        btn_b.clicked.connect(self.launch_project_b)
        layout.addWidget(btn_b)
        
        btn_c = QPushButton("Project C: Full Companion")
        btn_c.setMinimumHeight(50)
        btn_c.clicked.connect(self.launch_project_c)
        layout.addWidget(btn_c)
        
        layout.addStretch()
    
    def launch_project_a(self):
        """Launch Project A (Basic Assistant with Ollama)."""
        print("Launching Project A: Basic Assistant...")
        
        system_prompt = (
            "You are Aura, a friendly and helpful AI assistant. "
            "Provide clear, concise answers and be supportive."
        )
        
        self.chat_window = OllamaChatWindow("Project A: Basic Assistant", system_prompt)
        self.chat_window.show()
        self.close()
    
    def launch_project_b(self):
        """Launch Project B (Interactive Storyteller with character interactions)."""
        print("Launching Project B: Interactive Storyteller...")
        
        system_prompt = (
            "You are a creative storytelling assistant. "
            "Help create engaging stories, roleplay scenarios, and character interactions. "
            "Be imaginative, expressive, and maintain consistent character personalities."
        )
        
        self.chat_window = OllamaChatWindow("Project B: Interactive Storyteller", system_prompt)
        self.chat_window.show()
        self.close()
    
    def launch_project_c(self):
        """Launch Project C (Full Companion with all features)."""
        print("Launching Project C: Full Companion...")
        
        system_prompt = (
            "You are Aura, a comprehensive AI companion. "
            "Provide helpful assistance across all domains: conversation, creative writing, "
            "technical help, emotional support, and more. Be warm, intelligent, and adaptive."
        )
        
        self.chat_window = OllamaChatWindow("Project C: Full Companion", system_prompt)
        self.chat_window.show()
        self.close()


def main():
    """Main entry point for AuraNexus."""
    print("Initializing AuraNexus...")
    
    app = QApplication(sys.argv)
    
    launcher = ProjectLauncher()
    launcher.show()
    
    print("✓ Application ready")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
