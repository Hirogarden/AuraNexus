"""Demo application for structured outputs and tool calling."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from ollama_chat import OllamaChatWindow


class ToolDemoWindow(OllamaChatWindow):
    """Extended chat window with tool calling demonstrations."""
    
    def __init__(self):
        # System prompt that encourages tool use
        system_prompt = """You are Aura, an AI assistant with access to tools.

When the user asks you to perform calculations, check the time, or list files, 
USE THE AVAILABLE TOOLS instead of trying to answer directly.

Available tools:
- get_current_time: Get the current date and time
- calculate: Perform math calculations (supports +, -, *, /, sqrt, sin, cos, etc.)
- list_files: List files in a directory

Always use tools when appropriate to give accurate, real-time information."""
        
        super().__init__(project_name="Tool Calling Demo", system_prompt=system_prompt)
        
        # Auto-select tool-capable model (prefer llama3.2, llama3.1, mistral)
        available_models = self.client.list_models()
        tool_capable_models = ['llama3.2:latest', 'llama3.2', 'llama3.1', 'llama3.1:latest', 'mistral', 'mistral:latest']
        
        selected_model = None
        # Try to find a tool-capable model
        for preferred in tool_capable_models:
            if any(preferred in model for model in available_models):
                selected_model = next(m for m in available_models if preferred in m)
                break
        
        # Fallback to first model if no tool-capable model found
        if not selected_model and available_models:
            selected_model = available_models[0]
            self.append_message("system", 
                f"⚠️  Warning: Model '{selected_model}' may not support tool calling.\n"
                f"For best results, use llama3.2, llama3.1, or mistral.")
        
        if selected_model:
            self.client.model = selected_model
            self.model_combo.setCurrentText(selected_model)
        
        # Enable tools by default
        self.setup_tools()
        self.enable_tools()
        
        # Add welcome message
        self.append_message("system", 
            f"🛠️  Tool Calling Demo Loaded!\n\n"
            f"Model: {self.client.model}\n\n"
            f"This demo shows structured outputs and function calling.\n\n"
            f"Try these commands:\n"
            f"  • 'What time is it?'\n"
            f"  • 'Calculate sqrt(144) + 5'\n"
            f"  • 'List files in C:/'\n"
            f"  • 'Create a JSON profile for Bob, age 30'\n"
            f"  • 'What's 25 * 17 and what time is it?'"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    window = ToolDemoWindow()
    window.show()
    
    sys.exit(app.exec())
