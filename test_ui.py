"""Test the new UI controls for tool calling and JSON mode."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from ollama_chat import OllamaChatWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = OllamaChatWindow(
        project_name="UI Test",
        system_prompt="You are a helpful AI assistant with access to tools and structured outputs."
    )
    window.show()
    
    sys.exit(app.exec())
