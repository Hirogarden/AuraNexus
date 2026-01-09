"""Secure chat window using in-process inference engine.

HIPAA-compliant implementation with no external processes or network calls.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLineEdit, QLabel, QComboBox, QGroupBox, 
    QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from typing import List, Dict, Any
import json
from pathlib import Path
from datetime import datetime

from secure_inference_engine import SecureInferenceEngine


class SecureChatWorker(QThread):
    """Worker thread for secure inference to avoid blocking UI."""
    
    finished = Signal(dict)
    error = Signal(str)
    chunk = Signal(str)  # For streaming responses
    
    def __init__(self, engine: SecureInferenceEngine, messages: List[Dict[str, str]], 
                 model_name: str, **kwargs):
        super().__init__()
        self.engine = engine
        self.messages = messages
        self.model_name = model_name
        self.kwargs = kwargs
    
    def run(self):
        """Execute the inference request."""
        try:
            # Check if model is loaded
            if not self.engine.model or self.engine.current_model_name != self.model_name:
                success, message = self.engine.load_model(self.model_name)
                if not success:
                    self.error.emit(f"Failed to load model: {message}")
                    return
            
            # Generate response with streaming
            response_text = ""
            for chunk in self.engine.chat(self.messages, stream=True, **self.kwargs):
                if "content" in chunk:
                    response_text += chunk["content"]
                    self.chunk.emit(chunk["content"])
            
            # Emit complete response
            self.finished.emit({
                "role": "assistant",
                "content": response_text,
                "model": self.model_name
            })
            
        except Exception as e:
            self.error.emit(str(e))


class SecureChatWindow(QMainWindow):
    """Secure chat window with in-process inference."""
    
    def __init__(self, project_name: str, system_prompt: str = None, model_path: Path = None):
        super().__init__()
        self.project_name = project_name
        self.setWindowTitle(f"AuraNexus Secure - {project_name}")
        self.resize(1000, 700)
        
        # Initialize secure inference engine
        self.engine = SecureInferenceEngine()
        self.messages: List[Dict[str, str]] = []
        self.system_prompt = system_prompt or "You are Aura, a friendly and helpful AI assistant."
        self.worker = None
        self.current_response = ""
        
        # Model management
        self.models_dir = Path(__file__).parent.parent / "engines" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.current_model = None
        
        # Initialize UI
        self._init_ui()
        
        # Load initial model if specified
        if model_path and model_path.exists():
            self.load_model(model_path)
        else:
            self._scan_models()
    
    def _init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # === Model Selection ===
        model_group = QGroupBox("Model Configuration")
        model_layout = QHBoxLayout()
        
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo)
        
        self.load_model_btn = QPushButton("Load Model")
        self.load_model_btn.clicked.connect(self._load_selected_model)
        model_layout.addWidget(self.load_model_btn)
        
        self.browse_model_btn = QPushButton("Browse...")
        self.browse_model_btn.clicked.connect(self._browse_model)
        model_layout.addWidget(self.browse_model_btn)
        
        model_layout.addStretch()
        model_group.setLayout(model_layout)
        main_layout.addWidget(model_group)
        
        # === Sampling Parameters ===
        params_group = QGroupBox("Sampling Parameters")
        params_layout = QVBoxLayout()
        
        # Row 1: Temperature, Top-K, Top-P
        row1 = QHBoxLayout()
        
        row1.addWidget(QLabel("Temp:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        row1.addWidget(self.temperature_spin)
        
        row1.addWidget(QLabel("Top-K:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(0, 100)
        self.top_k_spin.setValue(40)
        row1.addWidget(self.top_k_spin)
        
        row1.addWidget(QLabel("Top-P:"))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(0.9)
        row1.addWidget(self.top_p_spin)
        
        row1.addWidget(QLabel("Min-P:"))
        self.min_p_spin = QDoubleSpinBox()
        self.min_p_spin.setRange(0.0, 1.0)
        self.min_p_spin.setSingleStep(0.05)
        self.min_p_spin.setValue(0.05)
        row1.addWidget(self.min_p_spin)
        
        row1.addStretch()
        params_layout.addLayout(row1)
        
        # Row 2: Repetition Penalty, Max Tokens
        row2 = QHBoxLayout()
        
        row2.addWidget(QLabel("Rep Penalty:"))
        self.repeat_penalty_spin = QDoubleSpinBox()
        self.repeat_penalty_spin.setRange(1.0, 2.0)
        self.repeat_penalty_spin.setSingleStep(0.05)
        self.repeat_penalty_spin.setValue(1.1)
        row2.addWidget(self.repeat_penalty_spin)
        
        row2.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 8192)
        self.max_tokens_spin.setValue(512)
        row2.addWidget(self.max_tokens_spin)
        
        # Advanced checkboxes
        self.dry_enabled = QCheckBox("DRY Sampling")
        self.dry_enabled.setToolTip("Enable DRY (Don't Repeat Yourself) sampling")
        row2.addWidget(self.dry_enabled)
        
        self.xtc_enabled = QCheckBox("XTC Sampling")
        self.xtc_enabled.setToolTip("Enable XTC (eXclude Top Choices) sampling")
        row2.addWidget(self.xtc_enabled)
        
        row2.addStretch()
        params_layout.addLayout(row2)
        
        params_group.setLayout(params_layout)
        main_layout.addWidget(params_group)
        
        # === Chat Display ===
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(self.chat_display, stretch=1)
        
        # === Input Area ===
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field, stretch=1)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_chat)
        input_layout.addWidget(self.clear_btn)
        
        main_layout.addLayout(input_layout)
        
        # === Status Bar ===
        self.statusBar().showMessage("Ready - No model loaded")
    
    def _scan_models(self):
        """Scan models directory for GGUF files."""
        self.model_combo.clear()
        
        if not self.models_dir.exists():
            self.statusBar().showMessage(f"Models directory not found: {self.models_dir}")
            return
        
        gguf_files = list(self.models_dir.glob("*.gguf"))
        
        if not gguf_files:
            self.statusBar().showMessage(f"No GGUF models found in {self.models_dir}")
            self.model_combo.addItem("(No models found)")
            return
        
        for model_file in sorted(gguf_files):
            self.model_combo.addItem(model_file.name, model_file)
        
        self.statusBar().showMessage(f"Found {len(gguf_files)} model(s)")
    
    def _on_model_changed(self, model_name: str):
        """Handle model selection change."""
        if model_name and model_name != "(No models found)":
            self.statusBar().showMessage(f"Selected: {model_name} (not loaded)")
    
    def _load_selected_model(self):
        """Load the currently selected model."""
        if self.model_combo.count() == 0:
            QMessageBox.warning(self, "No Models", "No models available to load.")
            return
        
        model_data = self.model_combo.currentData()
        if not model_data or not isinstance(model_data, Path):
            return
        
        self.load_model(model_data)
    
    def _browse_model(self):
        """Browse for a GGUF model file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GGUF Model",
            str(self.models_dir),
            "GGUF Models (*.gguf);;All Files (*.*)"
        )
        
        if file_path:
            self.load_model(Path(file_path))
    
    def load_model(self, model_path: Path):
        """Load a model into the inference engine."""
        self.statusBar().showMessage(f"Loading {model_path.name}...")
        self.load_model_btn.setEnabled(False)
        
        try:
            success, message = self.engine.load_model(str(model_path))
            
            if success:
                self.current_model = model_path
                self.statusBar().showMessage(f"Ready - {model_path.name}")
                self._append_system_message(f"Model loaded: {model_path.name}")
            else:
                self.statusBar().showMessage(f"Failed to load model")
                QMessageBox.critical(self, "Model Load Error", message)
        
        except Exception as e:
            self.statusBar().showMessage("Error loading model")
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")
        
        finally:
            self.load_model_btn.setEnabled(True)
    
    def _send_message(self):
        """Send a message to the model."""
        if not self.current_model:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return
        
        user_input = self.input_field.text().strip()
        if not user_input:
            return
        
        # Append user message to display
        self._append_message("User", user_input)
        self.input_field.clear()
        
        # Add to message history
        self.messages.append({"role": "user", "content": user_input})
        
        # Prepare messages with system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}] + self.messages
        
        # Collect sampling parameters
        kwargs = {
            "temperature": self.temperature_spin.value(),
            "top_k": self.top_k_spin.value(),
            "top_p": self.top_p_spin.value(),
            "min_p": self.min_p_spin.value(),
            "repeat_penalty": self.repeat_penalty_spin.value(),
            "max_tokens": self.max_tokens_spin.value(),
        }
        
        # Add advanced sampling if enabled
        if self.dry_enabled.isChecked():
            kwargs["dry_multiplier"] = 0.8
            kwargs["dry_base"] = 1.75
        
        if self.xtc_enabled.isChecked():
            kwargs["xtc_probability"] = 0.1
            kwargs["xtc_threshold"] = 0.1
        
        # Start worker thread
        self.current_response = ""
        self._append_message("Aura", "")  # Placeholder for streaming
        
        self.worker = SecureChatWorker(
            self.engine,
            full_messages,
            self.current_model.name,
            **kwargs
        )
        self.worker.chunk.connect(self._on_response_chunk)
        self.worker.finished.connect(self._on_response_finished)
        self.worker.error.connect(self._on_response_error)
        
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self.statusBar().showMessage("Generating...")
        
        self.worker.start()
    
    def _on_response_chunk(self, chunk: str):
        """Handle streaming response chunks."""
        self.current_response += chunk
        
        # Update the last message in the display
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor)
        
        # Replace assistant message content
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertHtml(f"<b>Aura:</b> {self._format_message_html(self.current_response)}<br>")
        
        # Scroll to bottom
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def _on_response_finished(self, response: Dict[str, Any]):
        """Handle complete response."""
        self.messages.append(response)
        
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self.statusBar().showMessage("Ready")
        
        self.current_response = ""
    
    def _on_response_error(self, error: str):
        """Handle inference error."""
        self._append_system_message(f"Error: {error}")
        
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.statusBar().showMessage("Error occurred")
    
    def _append_message(self, sender: str, content: str):
        """Append a message to the chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        formatted = self._format_message_html(content)
        cursor.insertHtml(f"<b>{sender}:</b> {formatted}<br>")
        
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def _append_system_message(self, content: str):
        """Append a system message to the chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(f"<i style='color: gray;'>[System: {content}]</i><br>")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def _format_message_html(self, content: str) -> str:
        """Format message content for HTML display."""
        # Escape HTML
        content = content.replace("&", "&amp;")
        content = content.replace("<", "&lt;")
        content = content.replace(">", "&gt;")
        
        # Convert newlines to breaks
        content = content.replace("\n", "<br>")
        
        return content
    
    def _clear_chat(self):
        """Clear the chat history."""
        reply = QMessageBox.question(
            self,
            "Clear Chat",
            "Are you sure you want to clear the chat history?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.messages.clear()
            self.chat_display.clear()
            self._append_system_message("Chat cleared")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Unload model to free memory
        if self.engine.model:
            self.engine.unload_model()
        
        event.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = SecureChatWindow("Test Chat")
    window.show()
    sys.exit(app.exec())
