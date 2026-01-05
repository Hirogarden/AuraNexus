"""AuraNexus - Unified Entry Point
Provides a launcher to select between:
- Project A: Basic Assistant (Local LLM)
- Project B: Interactive Storyteller (SillyTavern integration)
- Project C: Full Companion (All features)
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from llm.model_manager import ModelManager
from llm.conversation import ConversationManager
from ui.chat_window import ChatWindow


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
        """Launch Project A (Basic Assistant with local LLM)."""
        print("Launching Project A: Basic Assistant...")
        
        # Create conversation and model managers
        conversation_manager = ConversationManager()
        print("✓ Conversation manager initialized")
        
        # Create and load LLM model
        llm_manager = ModelManager()
        print(f"Loading model from: {llm_manager.model_path}")
        
        if not llm_manager.load_model():
            QMessageBox.critical(
                self,
                "Model Loading Error",
                f"Failed to load the AI model.\n\n"
                f"Expected location: {llm_manager.model_path}\n\n"
                f"Please ensure Mistral 7B GGUF model is in the models/ directory.\n"
                f"Download from: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF"
            )
            return
        
        print("✓ Model loaded successfully")
        
        # Create and show chat window
        self.chat_window = ChatWindow(llm_manager, conversation_manager)
        self.chat_window.setWindowTitle("AuraNexus - Project A: Basic Assistant")
        self.chat_window.show()
        self.close()
    
    def launch_project_b(self):
        """Launch Project B (Interactive Storyteller with SillyTavern)."""
        QMessageBox.information(
            self,
            "Project B",
            "Interactive Storyteller mode.\n\n"
            "This will integrate with SillyTavern for character interactions.\n"
            "Feature coming soon!"
        )
    
    def launch_project_c(self):
        """Launch Project C (Full Companion with all features)."""
        QMessageBox.information(
            self,
            "Project C",
            "Full Companion mode.\n\n"
            "This includes avatar integration, image generation, and all features.\n"
            "Feature coming soon!"
        )


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
