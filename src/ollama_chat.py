"""Simple chat window using Ollama backend."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLineEdit, QLabel, QComboBox, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from typing import List
import json
from pathlib import Path
from datetime import datetime

from ollama_client import OllamaClient, Message
from vram_optimizer import VRAMMonitor, LowVRAMOptimizer, get_system_vram_info
from memory_estimator import MemoryEstimator
from time_utils import (
    calculate_time_elapsed,
    format_time_elapsed,
    generate_time_context_prompt,
    format_timestamp_for_display,
    should_acknowledge_time_gap
)
from vram_monitor import VRAMMonitoringSession, VRAMThresholds, get_current_vram_usage
from gguf_architecture import ArchitectureDetector, ModelMetadata, Architecture

# RAG imports (optional) - DISABLED FOR NOW due to slow torch/transformers imports
# TODO: Make builtin_rag lazy-load dependencies
RAG_AVAILABLE = False
BuiltInRAG = None
# try:
#     from builtin_rag import BuiltInRAG, RAG_AVAILABLE
# except Exception as e:
#     RAG_AVAILABLE = False
#     BuiltInRAG = None
#     print(f"Warning: RAG functionality disabled due to import error: {e}")

try:
    from anythingllm_client import AnythingLLMClient
    ANYTHINGLLM_AVAILABLE = True
except Exception as e:
    ANYTHINGLLM_AVAILABLE = False
    AnythingLLMClient = None
    print(f"Warning: AnythingLLM functionality disabled due to import error: {e}")


class ChatWorker(QThread):
    """Worker thread for Ollama chat to avoid blocking UI."""
    
    finished = Signal(dict)  # Changed from str to dict
    error = Signal(str)
    token = Signal(str)  # For streaming individual tokens
    tool_call = Signal(dict)  # For tool execution requests
    
    def __init__(self, client: OllamaClient, messages: List[Message], system_prompt: str, 
                 stream: bool = True, options: dict = None, format: dict = None, tools: list = None):
        super().__init__()
        self.client = client
        self.messages = messages
        self.system_prompt = system_prompt
        self.stream = stream
        self.options = options or {}
        self.format = format
        self.tools = tools
        self.cancelled = False
    
    def run(self):
        """Run chat request in background thread."""
        try:
            if self.cancelled:
                return
            
            if self.stream:
                full_response = ""
                tool_calls = []
                for chunk in self.client.chat_stream(self.messages, 
                                                     system_prompt=self.system_prompt,
                                                     options=self.options,
                                                     format=self.format,
                                                     tools=self.tools):
                    if self.cancelled:
                        return
                    
                    # Handle dict chunks
                    if isinstance(chunk, dict):
                        content = chunk.get("content", "")
                        if content:
                            full_response += content
                            self.token.emit(content)
                        
                        # Check for tool calls in final chunk
                        if chunk.get("done") and chunk.get("tool_calls"):
                            tool_calls = chunk["tool_calls"]
                    else:
                        # Backward compatibility with string chunks
                        full_response += chunk
                        self.token.emit(chunk)
                
                if not self.cancelled:
                    result = {"content": full_response}
                    if tool_calls:
                        result["tool_calls"] = tool_calls
                    self.finished.emit(result)
            else:
                response = self.client.chat(self.messages, 
                                           system_prompt=self.system_prompt,
                                           options=self.options,
                                           format=self.format,
                                           tools=self.tools)
                if not self.cancelled:
                    self.finished.emit(response)
        except Exception as e:
            if not self.cancelled:
                # If tool calling failed with 400 error, retry without tools
                error_str = str(e)
                if "400" in error_str and self.tools:
                    try:
                        # Retry without tools
                        response = self.client.chat(self.messages, 
                                                   system_prompt=self.system_prompt,
                                                   options=self.options,
                                                   format=None,  # Also disable format
                                                   tools=None)
                        if not self.cancelled:
                            # Add warning to response
                            response["content"] = (
                                "[Note: Tool calling not supported by this model. Responding without tools.]\\n\\n" +
                                response.get("content", "")
                            )
                            self.finished.emit(response)
                            return
                    except Exception:
                        pass  # Fall through to emit original error
                
                self.error.emit(error_str)
    
    def cancel(self):
        """Cancel the request."""
        self.cancelled = True


class OllamaChatWindow(QMainWindow):
    """Simple chat window for Ollama-based projects."""
    
    def __init__(self, project_name: str, system_prompt: str = None):
        super().__init__()
        self.project_name = project_name
        self.setWindowTitle(f"AuraNexus - {project_name}")
        self.resize(800, 600)
        
        # Initialize Ollama client
        self.client = OllamaClient()
        self.messages: List[Message] = []
        self.system_prompt = system_prompt or "You are Aura, a friendly and helpful AI assistant."
        self.worker = None
        self.current_response = ""  # Track streaming response
        
        # Initialize VRAM optimizer and memory estimator
        self.vram_monitor = VRAMMonitor()
        self.vram_optimizer = LowVRAMOptimizer()
        self.vram_info = get_system_vram_info()
        self.memory_estimator = MemoryEstimator()
        
        # Initialize real-time VRAM monitoring
        self.vram_monitoring_session = None
        self.vram_monitoring_enabled = False
        
        # Initialize RAG systems
        self.builtin_rag = None
        self.anythingllm = None
        self.rag_mode = "none"  # none, builtin, anythingllm
        
        # Try to initialize built-in RAG
        if RAG_AVAILABLE:
            try:
                self.builtin_rag = BuiltInRAG()
                self.rag_mode = "builtin"
            except Exception as e:
                print(f"Built-in RAG not available: {e}")
        
        # Try to detect AnythingLLM
        if ANYTHINGLLM_AVAILABLE:
            try:
                self.anythingllm = AnythingLLMClient()
                if self.anythingllm.is_available():
                    # Don't auto-switch, let user choose
                    pass
            except Exception:
                pass
        
        # Initialize tools (must be before setup_ui)
        self.setup_tools()
        
        self.setup_ui()
        self.load_models()
    
    def setup_ui(self):
        """Setup the chat UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Model selection and management
        model_group = QGroupBox("Model & Settings")
        model_main_layout = QVBoxLayout(model_group)
        
        # First row: Model selector and management buttons
        model_row1 = QHBoxLayout()
        model_row1.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        model_row1.addWidget(self.model_combo, 1)
        
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setMaximumWidth(40)
        self.refresh_models_btn.setToolTip("Refresh model list")
        self.refresh_models_btn.clicked.connect(self.load_models)
        model_row1.addWidget(self.refresh_models_btn)
        
        self.pull_model_btn = QPushButton("📥")
        self.pull_model_btn.setMaximumWidth(40)
        self.pull_model_btn.setToolTip("Download new model")
        self.pull_model_btn.clicked.connect(self.pull_model_dialog)
        model_row1.addWidget(self.pull_model_btn)
        
        self.delete_model_btn = QPushButton("🗑️")
        self.delete_model_btn.setMaximumWidth(40)
        self.delete_model_btn.setToolTip("Delete selected model")
        self.delete_model_btn.clicked.connect(self.delete_model_dialog)
        model_row1.addWidget(self.delete_model_btn)
        
        self.info_model_btn = QPushButton("ℹ️")
        self.info_model_btn.setMaximumWidth(40)
        self.info_model_btn.setToolTip("Model information")
        self.info_model_btn.clicked.connect(self.show_model_info)
        model_row1.addWidget(self.info_model_btn)
        
        self.import_model_btn = QPushButton("📂")
        self.import_model_btn.setMaximumWidth(40)
        self.import_model_btn.setToolTip("Import existing GGUF model")
        self.import_model_btn.clicked.connect(self.import_model_dialog)
        model_row1.addWidget(self.import_model_btn)
        
        # RAG mode selection
        model_row1.addWidget(QLabel("Memory:"))
        self.rag_combo = QComboBox()
        self.rag_combo.addItem("None", "none")
        if self.builtin_rag:
            self.rag_combo.addItem("Built-in RAG", "builtin")
        if self.anythingllm and self.anythingllm.is_available():
            self.rag_combo.addItem("AnythingLLM", "anythingllm")
        self.rag_combo.currentIndexChanged.connect(self.on_rag_mode_changed)
        model_row1.addWidget(self.rag_combo)
        
        model_main_layout.addLayout(model_row1)
        
        # Second row: Parameter controls
        from PySide6.QtWidgets import QSlider, QCheckBox
        params_row = QHBoxLayout()
        
        # Temperature
        params_row.addWidget(QLabel("Temp:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setMinimum(0)
        self.temp_slider.setMaximum(200)
        self.temp_slider.setValue(80)
        self.temp_slider.setMaximumWidth(100)
        self.temp_slider.setToolTip("Temperature (creativity): 0.0-2.0")
        params_row.addWidget(self.temp_slider)
        self.temp_label = QLabel("0.8")
        self.temp_label.setMinimumWidth(30)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.1f}"))
        params_row.addWidget(self.temp_label)
        
        # Top K
        params_row.addWidget(QLabel("TopK:"))
        self.topk_slider = QSlider(Qt.Horizontal)
        self.topk_slider.setMinimum(1)
        self.topk_slider.setMaximum(100)
        self.topk_slider.setValue(40)
        self.topk_slider.setMaximumWidth(100)
        self.topk_slider.setToolTip("Top K sampling: 1-100")
        params_row.addWidget(self.topk_slider)
        self.topk_label = QLabel("40")
        self.topk_label.setMinimumWidth(30)
        self.topk_slider.valueChanged.connect(lambda v: self.topk_label.setText(str(v)))
        params_row.addWidget(self.topk_label)
        
        # Top P
        params_row.addWidget(QLabel("TopP:"))
        self.topp_slider = QSlider(Qt.Horizontal)
        self.topp_slider.setMinimum(0)
        self.topp_slider.setMaximum(100)
        self.topp_slider.setValue(90)
        self.topp_slider.setMaximumWidth(100)
        self.topp_slider.setToolTip("Top P (nucleus sampling): 0.0-1.0")
        params_row.addWidget(self.topp_slider)
        self.topp_label = QLabel("0.9")
        self.topp_label.setMinimumWidth(30)
        self.topp_slider.valueChanged.connect(lambda v: self.topp_label.setText(f"{v/100:.1f}"))
        params_row.addWidget(self.topp_label)
        
        # Streaming toggle
        self.streaming_checkbox = QCheckBox("Stream")
        self.streaming_checkbox.setChecked(True)
        self.streaming_checkbox.setToolTip("Enable real-time streaming responses")
        params_row.addWidget(self.streaming_checkbox)
        
        # Timestamp toggle
        self.timestamps_checkbox = QCheckBox("⏰ Timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.timestamps_checkbox.setToolTip("Show message timestamps and enable time-aware context")
        params_row.addWidget(self.timestamps_checkbox)
        
        params_row.addStretch()
        model_main_layout.addLayout(params_row)
        
        layout.addWidget(model_group)
        
        # AI Features group (Tool Calling & Structured Outputs)
        features_group = QGroupBox("AI Features")
        features_layout = QHBoxLayout(features_group)
        
        # Tool calling toggle
        self.tools_checkbox = QCheckBox("🛠️ Tool Calling")
        self.tools_checkbox.setToolTip("Enable function calling (time, calculator, file listing)")
        self.tools_checkbox.stateChanged.connect(self.on_tools_toggled)
        features_layout.addWidget(self.tools_checkbox)
        
        # JSON mode toggle
        self.json_checkbox = QCheckBox("📋 JSON Mode")
        self.json_checkbox.setToolTip("Force model to return valid JSON")
        self.json_checkbox.stateChanged.connect(self.on_json_toggled)
        features_layout.addWidget(self.json_checkbox)
        
        # Schema button (only enabled when JSON mode is on)
        self.schema_button = QPushButton("Schema...")
        self.schema_button.setToolTip("Define custom JSON schema for structured outputs")
        self.schema_button.setEnabled(False)
        self.schema_button.clicked.connect(self.edit_json_schema)
        features_layout.addWidget(self.schema_button)
        
        # Status indicator label
        self.features_status = QLabel("")
        self.features_status.setStyleSheet("color: gray; font-style: italic;")
        features_layout.addWidget(self.features_status, 1)
        
        features_layout.addStretch()
        layout.addWidget(features_group)
        
        # Model Memory Management group
        memory_group = QGroupBox("Memory Management")
        memory_layout = QHBoxLayout(memory_group)
        
        # Show loaded models button
        self.show_loaded_button = QPushButton("🔍 Show Loaded Models")
        self.show_loaded_button.setToolTip("View models currently in memory")
        self.show_loaded_button.clicked.connect(self.show_loaded_models)
        memory_layout.addWidget(self.show_loaded_button)
        
        # Unload current model button
        self.unload_button = QPushButton("💾 Unload Current Model")
        self.unload_button.setToolTip("Free memory by unloading the current model")
        self.unload_button.clicked.connect(self.unload_current_model)
        memory_layout.addWidget(self.unload_button)
        
        # Keep alive setting
        memory_layout.addWidget(QLabel("Keep Alive:"))
        self.keep_alive_input = QLineEdit()
        self.keep_alive_input.setPlaceholderText("5m")
        self.keep_alive_input.setToolTip("How long to keep model in memory (e.g., 5m, 1h, 0=immediate unload)")
        self.keep_alive_input.setMaximumWidth(80)
        memory_layout.addWidget(self.keep_alive_input)
        
        # Memory status label
        self.memory_status = QLabel("")
        self.memory_status.setStyleSheet("color: gray; font-style: italic;")
        memory_layout.addWidget(self.memory_status, 1)
        
        memory_layout.addStretch()
        # Real-time VRAM monitoring toggle
        self.vram_monitor_checkbox = QCheckBox("📊 Real-time VRAM Monitoring")
        self.vram_monitor_checkbox.setToolTip("Monitor VRAM usage during inference (updates every second)")
        self.vram_monitor_checkbox.stateChanged.connect(self.on_vram_monitoring_toggled)
        memory_layout.addWidget(self.vram_monitor_checkbox)
        
        # Real-time VRAM display
        self.vram_live_label = QLabel("VRAM: --")
        self.vram_live_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        self.vram_live_label.setToolTip("Current VRAM usage")
        memory_layout.addWidget(self.vram_live_label)
        
        memory_layout.addStretch()
        layout.addWidget(memory_group)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        font = QFont("Consolas", 10)
        self.chat_display.setFont(font)
        layout.addWidget(self.chat_display, 1)
        
        # Input area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field, 1)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_request)
        self.cancel_button.setEnabled(False)
        input_layout.addWidget(self.cancel_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_chat)
        input_layout.addWidget(self.clear_button)
        
        layout.addLayout(input_layout)
        
        # Save/Load buttons
        file_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Conversation")
        self.save_button.clicked.connect(self.save_conversation)
        file_layout.addWidget(self.save_button)
        
        self.load_button = QPushButton("Load Conversation")
        self.load_button.clicked.connect(self.load_conversation)
        file_layout.addWidget(self.load_button)
        
        self.save_to_memory_button = QPushButton("Save to Memory")
        self.save_to_memory_button.clicked.connect(self.save_to_memory)
        self.save_to_memory_button.setEnabled(self.rag_mode != "none")
        file_layout.addWidget(self.save_to_memory_button)
        
        layout.addLayout(file_layout)
        
        # Status bar with VRAM info
        self.statusBar().showMessage("Ready")
        self.update_vram_status()
    
    def update_vram_status(self):
        """Update VRAM status in status bar."""
        vram_summary = self.vram_monitor.get_vram_summary()
        self.statusBar().showMessage(f"Ready | {vram_summary}")
    
    def load_models(self):
        """Load available Ollama models with retry logic."""
        # Clear existing items to prevent duplication
        self.model_combo.clear()
        
        # Try a few times in case Ollama just started
        max_retries = 3
        for attempt in range(max_retries):
            models = self.client.list_models()
            if models:
                self.model_combo.addItems(models)
                self.update_vram_status()
                return
            
            # Wait a bit before retrying (except on last attempt)
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
        
        # If we get here, couldn't connect
        self.model_combo.addItem("llama3")
        self.statusBar().showMessage("Could not connect to Ollama - check if Ollama is running")
    
    def append_message(self, role: str, content: str, timestamp: datetime = None):
        """Append a message to the chat display with optional timestamp."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Format timestamp if provided and feature is enabled
        time_str = ""
        if timestamp and self.timestamps_checkbox.isChecked():
            time_str = f" ({format_timestamp_for_display(timestamp)})"
        
        if role == "user":
            cursor.insertText(f"\n🧑 You{time_str}:\n{content}\n")
        elif role == "assistant":
            cursor.insertText(f"\n🤖 Aura{time_str}:\n{content}\n")
        else:
            cursor.insertText(f"\n[{role}{time_str}]: {content}\n")
        
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def send_message(self):
        """Send user message and get response."""
        user_input = self.input_field.text().strip()
        if not user_input:
            return
        
        # Check VRAM before processing (for large models)
        model_name = self.model_combo.currentText()
        model_info = self.client.show_model(model_name)
        if model_info and 'size' in model_info:
            size_gb = model_info['size'] / (1024**3)
            can_fit, msg = self.vram_monitor.can_fit_model(size_gb * 1024)
            
            if not can_fit and self.vram_optimizer.is_low_vram:
                # Show warning but allow to continue
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.warning(
                    self, "VRAM Warning",
                    f"{msg}\n\nThe model may run slowly or cause issues. Continue?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.input_field.clear()
        
        # Add user message with timestamp
        user_message = Message(role="user", content=user_input)
        self.messages.append(user_message)
        self.append_message("user", user_input, user_message.timestamp)
        
        # Generate time context if there are previous messages and feature is enabled
        time_context = ""
        if self.timestamps_checkbox.isChecked() and len(self.messages) > 1:
            # Find last user message before this one
            for msg in reversed(self.messages[:-1]):
                if msg.role == "user":
                    elapsed = calculate_time_elapsed(msg.timestamp, user_message.timestamp)
                    if should_acknowledge_time_gap(elapsed):
                        time_context = generate_time_context_prompt(msg.timestamp)
                    break
        
        # Show appropriate status based on model
        if "8b" in model_name.lower() or "7b" in model_name.lower():
            self.statusBar().showMessage("Loading model into VRAM... (first use may take 30-60s)")
        else:
            self.statusBar().showMessage("Thinking...")
        
        # Get RAG context if enabled
        rag_context = ""
        if self.rag_mode == "builtin" and self.builtin_rag:
            try:
                rag_context = self.builtin_rag.get_context(user_input, n_results=2)
                if rag_context:
                    self.statusBar().showMessage("Retrieving memories...")
            except Exception as e:
                print(f"RAG context error: {e}")
        
        # Augment system prompt with RAG context and time context
        augmented_prompt = self.system_prompt
        if rag_context:
            augmented_prompt = f"{self.system_prompt}\n\n{rag_context}\n\nUse the context above if relevant to the user's question."
        if time_context:
            augmented_prompt = f"{augmented_prompt}\n\n{time_context}"
        
        # Get selected model
        selected_model = self.model_combo.currentText()
        self.client.model = selected_model
        
        # Build options from UI controls
        options = {
            "temperature": self.temp_slider.value() / 100.0,
            "top_k": self.topk_slider.value(),
            "top_p": self.topp_slider.value() / 100.0,
            "num_predict": 512,  # Limit response length to prevent rambling
        }
        
        # Check if streaming enabled
        stream = self.streaming_checkbox.isChecked()
        
        # Get format and tools if they're set (will be None by default)
        format_schema = getattr(self, 'format_schema', None)
        tools = getattr(self, 'available_tools', None)
        
        # Start worker thread
        self.worker = ChatWorker(self.client, self.messages, augmented_prompt, stream, options, format_schema, tools)
        self.worker.finished.connect(self.on_response)
        self.worker.error.connect(self.on_error)
        
        if stream:
            self.current_response = ""
            # Start with assistant prefix for streaming
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText("\n🤖 Aura:\n")
            self.chat_display.setTextCursor(cursor)
            self.worker.token.connect(self.on_token)
        
        self.worker.start()
    
    def on_response(self, response: dict):
        """Handle successful response."""
        # Extract content from dict response
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        
        # Create assistant message with timestamp
        assistant_message = Message(
            role="assistant",
            content=content if not self.streaming_checkbox.isChecked() else self.current_response,
            tool_calls=tool_calls if tool_calls else None
        )
        
        if self.streaming_checkbox.isChecked():
            # For streaming, add timestamp after streamed response if enabled
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            if self.timestamps_checkbox.isChecked():
                time_str = format_timestamp_for_display(assistant_message.timestamp)
                cursor.insertText(f" ({time_str})\n")
            else:
                cursor.insertText("\n")
            self.chat_display.setTextCursor(cursor)
        else:
            # For non-streaming, append normally with timestamp
            self.append_message("assistant", content, assistant_message.timestamp)
        
        # Handle tool calls if present
        if tool_calls:
            self.handle_tool_calls(tool_calls)
        
        self.messages.append(assistant_message)
        
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.input_field.setFocus()
        self.update_vram_status()
    
    def on_token(self, token: str):
        """Handle streaming token."""
        self.current_response += token
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def on_error(self, error: str):
        """Handle error."""
        self.append_message("system", f"Error: {error}")
        
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.input_field.setFocus()
        self.statusBar().showMessage("Error occurred")
    
    def cancel_request(self):
        """Cancel the current request."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)  # Wait up to 1 second
            if self.worker.isRunning():
                self.worker.terminate()  # Force terminate if still running
            
            self.append_message("system", "Request cancelled")
            self.input_field.setEnabled(True)
            self.send_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("Cancelled")
            
            # Remove the last user message since it didn't get a response
            if self.messages and self.messages[-1].role == "user":
                self.messages.pop()
    
    def clear_chat(self):
        """Clear chat history."""
        self.messages.clear()
        self.chat_display.clear()
        self.statusBar().showMessage("Chat cleared")
    
    def save_conversation(self):
        """Save conversation to JSON file with timestamps."""
        if not self.messages:
            QMessageBox.information(self, "No Conversation", "No messages to save.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Conversation", 
            f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if filename:
            try:
                data = {
                    "project": self.project_name,
                    "system_prompt": self.system_prompt,
                    "model": self.model_combo.currentText(),
                    "timestamp": datetime.now().isoformat(),
                    "messages": [m.to_dict() for m in self.messages]  # Use to_dict() to preserve timestamps
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                self.statusBar().showMessage(f"Conversation saved to {Path(filename).name}")
                QMessageBox.information(self, "Saved", f"Conversation saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save conversation: {e}")
    
    def load_conversation(self):
        """Load conversation from JSON file with timestamps."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Conversation", "",
            "JSON Files (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Clear current conversation
                self.messages.clear()
                self.chat_display.clear()
                
                # Load messages with timestamps
                for msg_data in data.get("messages", []):
                    msg = Message.from_dict(msg_data)  # Use from_dict() to restore timestamps
                    self.messages.append(msg)
                    self.append_message(msg.role, msg.content, msg.timestamp)
                
                # Update model if available
                model = data.get("model", "")
                if model:
                    idx = self.model_combo.findText(model)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                
                self.statusBar().showMessage(f"Loaded conversation from {Path(filename).name}")
                QMessageBox.information(self, "Loaded", f"Conversation loaded successfully!\n{len(self.messages)} messages restored.")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load conversation: {e}")    
    def on_rag_mode_changed(self, index):
        """Handle RAG mode change."""
        self.rag_mode = self.rag_combo.itemData(index)
        self.save_to_memory_button.setEnabled(self.rag_mode != "none")
        
        status_text = {
            "none": "Memory disabled",
            "builtin": "Using built-in memory",
            "anythingllm": "Using AnythingLLM"
        }.get(self.rag_mode, "Unknown mode")
        
        self.statusBar().showMessage(status_text)
    
    def pull_model_dialog(self):
        """Show dialog to pull/download a new model."""
        from PySide6.QtWidgets import QInputDialog, QProgressDialog
        from PySide6.QtCore import QTimer
        
        model_name, ok = QInputDialog.getText(self, "Download Model", 
                                             "Enter model name (e.g., llama3, mistral):")
        if ok and model_name:
            progress = QProgressDialog("Downloading model...", "Cancel", 0, 0, self)
            progress.setWindowTitle("Pulling Model")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            status_text = []
            
            def update_progress():
                try:
                    status = next(pull_gen)
                    status_text.append(status)
                    progress.setLabelText(f"Downloading {model_name}...\\n{status}")
                    if progress.wasCanceled():
                        progress.close()
                        return
                    QTimer.singleShot(100, update_progress)
                except StopIteration:
                    progress.close()
                    QMessageBox.information(self, "Success", f"Model '{model_name}' downloaded successfully!")
                    self.load_models()
                except Exception as e:
                    progress.close()
                    QMessageBox.warning(self, "Error", f"Failed to download model: {e}")
            
            pull_gen = self.client.pull_model(model_name)
            QTimer.singleShot(100, update_progress)
    
    def delete_model_dialog(self):
        """Show dialog to delete selected model."""
        model_name = self.model_combo.currentText()
        if not model_name:
            QMessageBox.warning(self, "No Model", "Please select a model to delete.")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                    f"Are you sure you want to delete model '{model_name}'?\\nThis cannot be undone.",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.client.delete_model(model_name):
                QMessageBox.information(self, "Success", f"Model '{model_name}' deleted.")
                self.load_models()
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete model '{model_name}'.")
    
    def import_model_dialog(self):
        """Show dialog to import an existing GGUF model."""
        from PySide6.QtWidgets import QInputDialog
        import subprocess
        import tempfile
        
        # Select GGUF file
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select GGUF Model File", "",
            "GGUF Files (*.gguf);;All Files (*.*)"
        )
        
        if not filename:
            return
        
        # Validate file exists
        if not Path(filename).exists():
            QMessageBox.warning(self, "File Not Found", f"The selected file does not exist:\\n{filename}")
            return
        
        # Get model name from user
        model_name, ok = QInputDialog.getText(
            self, "Import Model",
            "Enter a name for this model:",
            text=Path(filename).stem
        )
        
        if not ok or not model_name:
            return
        
        # Clean up model name (remove special characters)
        model_name = model_name.strip().lower().replace(" ", "-")
        if not model_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid model name.")
            return
        
        # Add :latest tag if no tag specified
        if ":" not in model_name:
            model_name = f"{model_name}:latest"
        
        # Get file info for debugging
        file_path = Path(filename)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"DEBUG: Importing model '{model_name}' from '{filename}'")
        print(f"DEBUG: File size: {file_size_mb:.2f} MB")
        print(f"DEBUG: File exists: {file_path.exists()}")
        
        # Show progress dialog
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog("Preparing to import model...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Create temporary Modelfile
        modelfile_path = filename.replace('\\', '/')
        modelfile_content = f'FROM "{modelfile_path}"'
        
        print(f"DEBUG: Modelfile content: {modelfile_content}")
        
        try:
            # Write modelfile to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='_modelfile', delete=False) as f:
                f.write(modelfile_content)
                temp_modelfile = f.name
            
            print(f"DEBUG: Created temp modelfile: {temp_modelfile}")
            
            # Use ollama CLI command instead of API (API has issues in 0.13.5)
            import sys
            if sys.platform == "win32":
                cmd = ["ollama.exe", "create", model_name, "-f", temp_modelfile]
            else:
                cmd = ["ollama", "create", model_name, "-f", temp_modelfile]
            
            print(f"DEBUG: Running command: {' '.join(cmd)}")
            
            # Run the command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',  # Explicitly use UTF-8 to handle ollama's output
                errors='replace',  # Replace invalid characters instead of crashing
                bufsize=1
            )
            
            # Monitor progress
            output_lines = []
            while True:
                if progress.wasCanceled():
                    process.terminate()
                    print("DEBUG: Import canceled by user")
                    break
                
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if line:
                    line = line.strip()
                    output_lines.append(line)
                    print(f"DEBUG: {line}")
                    
                    # Update progress dialog with latest status
                    if line:
                        progress.setLabelText(f"Importing model '{model_name}'...\\n\\n{line}")
                
                # Process events to keep UI responsive
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            
            # Clean up temp file
            try:
                import os
                os.unlink(temp_modelfile)
            except:
                pass
            
            progress.close()
            
            # Check result
            if process.returncode == 0:
                QMessageBox.information(
                    self, "Import Complete",
                    f"Model '{model_name}' imported successfully!\\n\\nYou can now use it from the model dropdown."
                )
                self.load_models()
                # Select the newly imported model
                index = self.model_combo.findText(model_name)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
            else:
                error_msg = "\\n".join(output_lines[-10:])  # Last 10 lines
                QMessageBox.critical(
                    self, "Import Failed",
                    f"Failed to import model.\\n\\nOutput:\\n{error_msg}"
                )
                
        except Exception as e:
            print(f"DEBUG: Import failed with error: {e}")
            import traceback
            traceback.print_exc()
            progress.close()
            QMessageBox.critical(
                self, "Import Failed",
                f"Failed to import model:\\n\\n{str(e)}"
            )
    
    def show_model_info(self):
        """Show detailed information about selected model."""
        model_name = self.model_combo.currentText()
        if not model_name:
            QMessageBox.warning(self, "No Model", "Please select a model.")
            return
        
        info = self.client.show_model(model_name)
        if info:
            details = info.get("details", {})
            params = info.get("parameters", "N/A")
            family = details.get("family", "N/A")
            param_size = details.get("parameter_size", "N/A")
            quant = details.get("quantization_level", "N/A")
            size = info.get("size", 0)
            size_gb = size / (1024**3) if size > 0 else 0
            
            # Try to detect GGUF architecture if we can find the model file
            architecture_info = ""
            try:
                # Ollama stores models in ~/.ollama/models or C:\Users\<user>\.ollama\models
                from pathlib import Path
                import os
                
                # Common Ollama model paths
                if os.name == 'nt':  # Windows
                    ollama_dir = Path.home() / '.ollama' / 'models' / 'blobs'
                else:
                    ollama_dir = Path.home() / '.ollama' / 'models' / 'blobs'
                
                # Try to find GGUF file
                if ollama_dir.exists():
                    # Look for GGUF files (they're stored as blobs with sha256 names)
                    # This is a best-effort search - may not always work
                    for blob_file in ollama_dir.glob('sha256-*'):
                        # Check if it's likely a GGUF file (>100MB)
                        if blob_file.stat().st_size > 100 * 1024 * 1024:
                            try:
                                metadata = ArchitectureDetector.detect_from_file(str(blob_file))
                                if metadata.architecture != Architecture.UNKNOWN:
                                    hints = ArchitectureDetector.get_optimization_hints(metadata)
                                    
                                    architecture_info = f"""

🏗️  Architecture Analysis:
  Type: {metadata.architecture.value.upper()}
  Layers: {metadata.n_layer if metadata.n_layer else 'N/A'}
  Context: {f'{metadata.n_ctx:,}' if metadata.n_ctx else 'N/A'} tokens
  Embedding: {f'{metadata.n_embd}' if metadata.n_embd else 'N/A'} dim
  """
                                    if metadata.n_head:
                                        architecture_info += f"  Attention Heads: {metadata.n_head}"
                                        if metadata.has_gqa():
                                            architecture_info += f" (GQA: KV={metadata.n_head_kv}, ratio={metadata.get_kv_ratio():.2f})"
                                        architecture_info += "\n"
                                    
                                    if metadata.is_moe():
                                        architecture_info += f"  MoE: {metadata.n_expert} experts ({metadata.n_expert_used} active)\n"
                                    
                                    if metadata.is_rnn_style():
                                        architecture_info += "  Type: RNN-style (Efficient sequential processing)\n"
                                    
                                    architecture_info += f"""
  Optimization Hints:
    Flash Attention: {'Yes' if hints['supports_flash_attn'] else 'No'}
    KV Cache Multiplier: {hints['kv_cache_multiplier']:.2f}x
    Recommended Batch: {hints['recommended_batch_size']}
    Offload Priority: {hints['offload_priority']}"""
                                    break
                            except Exception:
                                continue
            except Exception:
                pass
            
            # Get VRAM optimization recommendations
            opt_params = self.vram_optimizer.get_optimal_params(size_gb)
            
            # Estimate memory requirements
            try:
                # Try to get quantization from model details
                modelfile = info.get('modelfile', '')
                ftype = quant if quant != 'N/A' else 'Q4_0'
                
                # Estimate based on file size
                if size_gb < 2:
                    mem_est = self.memory_estimator.estimate_from_params(32000, 2048, 2048, 22, ftype)
                elif size_gb < 5:
                    mem_est = self.memory_estimator.estimate_from_params(32000, 4096, 4096, 32, ftype)
                elif size_gb < 10:
                    mem_est = self.memory_estimator.estimate_from_params(32000, 4096, 5120, 40, ftype)
                else:
                    mem_est = self.memory_estimator.estimate_from_params(32000, 4096, 8192, 80, ftype)
                
                memory_info = f"""

💾 Memory Estimate:
  Total: {mem_est.total_gb:.2f} GB
  Embeddings: {mem_est.embeddings_mb:.0f} MB
  KV Cache: {mem_est.kv_cache_mb:.0f} MB
  Weights: {mem_est.weights_mb:.0f} MB"""
            except Exception:
                memory_info = ""
            
            info_text = f"""Model: {model_name}
            
Family: {family}
Parameters: {param_size}
Quantization: {quant}
Size: {size_gb:.2f} GB{architecture_info}{memory_info}

🎮 VRAM Optimization:
GPU Layers: {opt_params.gpu_layers}
Batch Size: {opt_params.n_batch}
Context: {opt_params.n_ctx}
Low VRAM Mode: {"Yes" if opt_params.low_vram_mode else "No"}
Reason: {opt_params.reason}

Parameters:
{params}"""
            
            QMessageBox.information(self, f"Model Info: {model_name}", info_text)
        else:
            QMessageBox.warning(self, "Error", f"Could not retrieve information for '{model_name}'.")
    
    def save_to_memory(self):
        """Save current conversation to RAG memory."""
        if not self.messages:
            QMessageBox.information(self, "No Conversation", "No messages to save to memory.")
            return
        
        if self.rag_mode == "none":
            QMessageBox.warning(self, "No Memory System", "Please select a memory system first.")
            return
        
        try:
            # Convert messages to dict format
            msg_dicts = [{"role": m.role, "content": m.content} for m in self.messages]
            
            if self.rag_mode == "builtin" and self.builtin_rag:
                doc_id = self.builtin_rag.add_conversation(
                    msg_dicts,
                    metadata={
                        "project": self.project_name,
                        "model": self.model_combo.currentText()
                    }
                )
                QMessageBox.information(
                    self, "Saved to Memory",
                    f"Conversation saved to built-in memory!\\n\\nID: {doc_id}\\n\\n"
                    f"This conversation can now be recalled in future chats."
                )
            
            elif self.rag_mode == "anythingllm" and self.anythingllm:
                # Format conversation as text
                conversation_text = f"Conversation from {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n\\n"
                conversation_text += "\\n\\n".join([
                    f"{msg['role'].upper()}: {msg['content']}"
                    for msg in msg_dicts
                ])
                
                success = self.anythingllm.add_document(
                    conversation_text,
                    f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                
                if success:
                    QMessageBox.information(
                        self, "Saved to Memory",
                        "Conversation saved to AnythingLLM!\\n\\n"
                        "It will be available for future RAG queries."
                    )
                else:
                    QMessageBox.warning(
                        self, "Save Failed",
                        "Failed to save to AnythingLLM. Check connection and API key."
                    )
            
            self.statusBar().showMessage("Conversation saved to memory")
        
        except Exception as e:
            QMessageBox.critical(self, "Memory Error", f"Failed to save to memory: {e}")
    
    # ========== Tool Calling Infrastructure ==========
    
    def setup_tools(self):
        """Initialize available tools for function calling."""
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current date and time",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Perform mathematical calculations. Supports basic arithmetic (+, -, *, /, **, %), trigonometry (sin, cos, tan), and common functions (sqrt, log, abs).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "The mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', 'sin(3.14159/2)')"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory path to list files from"
                            }
                        },
                        "required": ["directory"]
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool function and return the result."""
        try:
            if tool_name == "get_current_time":
                from datetime import datetime
                return f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            elif tool_name == "calculate":
                import math
                expression = arguments.get("expression", "")
                
                # Safe eval with limited namespace
                allowed_names = {
                    "abs": abs, "round": round, "min": min, "max": max,
                    "sum": sum, "pow": pow,
                    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                    "tan": math.tan, "log": math.log, "log10": math.log10,
                    "exp": math.exp, "pi": math.pi, "e": math.e
                }
                
                try:
                    result = eval(expression, {"__builtins__": {}}, allowed_names)
                    return f"Result: {result}"
                except Exception as e:
                    return f"Calculation error: {e}"
            
            elif tool_name == "list_files":
                import os
                directory = arguments.get("directory", ".")
                
                try:
                    files = os.listdir(directory)
                    return f"Files in {directory}:\\n" + "\\n".join(f"  - {f}" for f in files[:20])
                except Exception as e:
                    return f"Error listing files: {e}"
            
            else:
                return f"Unknown tool: {tool_name}"
        
        except Exception as e:
            return f"Tool execution error: {e}"
    
    def handle_tool_calls(self, tool_calls: list):
        """Handle tool calls from the model."""
        self.append_message("system", f"🔧 Executing {len(tool_calls)} tool(s)...")
        
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            tool_name = func.get("name", "unknown")
            arguments = func.get("arguments", {})
            
            self.append_message("system", f"  → {tool_name}({arguments})")
            
            # Execute the tool
            result = self.execute_tool(tool_name, arguments)
            
            self.append_message("system", f"  ✓ {result}")
            
            # Add tool result to message history
            self.messages.append(Message(
                role="tool",
                content=result,
                tool_name=tool_name
            ))
        
        # Automatically send follow-up to get model's response with tool results
        self.statusBar().showMessage("Processing tool results...")
        self.send_tool_followup()
    
    def send_tool_followup(self):
        """Send a follow-up request to let the model respond with tool results."""
        # Build options
        options = {
            "temperature": self.temp_slider.value() / 100.0,
            "top_k": self.topk_slider.value(),
            "top_p": self.topp_slider.value() / 100.0,
            "num_predict": 512,
        }
        
        stream = self.streaming_checkbox.isChecked()
        
        # Start worker with tools still available
        self.worker = ChatWorker(
            self.client, self.messages, self.system_prompt,
            stream, options, None, getattr(self, 'available_tools', None)
        )
        self.worker.finished.connect(self.on_response)
        self.worker.error.connect(self.on_error)
        
        if stream:
            self.current_response = ""
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText("\\n🤖 Aura:\\n")
            self.chat_display.setTextCursor(cursor)
            self.worker.token.connect(self.on_token)
        
        self.worker.start()
    
    def enable_tools(self):
        """Enable tool calling for the chat."""
        if not hasattr(self, 'available_tools'):
            self.setup_tools()
        
        # Check if current model supports tool calling
        model_name = self.model_combo.currentText().lower()
        tool_capable = any(name in model_name for name in ['llama3.2', 'llama3.1', 'mistral', 'command', 'qwen'])
        
        if not tool_capable:
            self.statusBar().showMessage(
                f"⚠️ Warning: {self.model_combo.currentText()} may not support tools. "
                "Try llama3.2, llama3.1, or mistral for best results."
            )
        else:
            self.statusBar().showMessage(f"Tool calling enabled ({len(self.available_tools)} tools available)")
    
    def disable_tools(self):
        """Disable tool calling."""
        self.available_tools = None
        self.statusBar().showMessage("Tool calling disabled")
    
    def set_json_format(self, schema: dict = None):
        """Enable JSON mode or structured outputs.
        
        Args:
            schema: Optional JSON schema for structured outputs.
                   If None, uses simple JSON mode.
        """
        if schema:
            self.format_schema = schema
            self.statusBar().showMessage("Structured output enabled")
        else:
            self.format_schema = "json"
            self.statusBar().showMessage("JSON mode enabled")
    
    def clear_format(self):
        """Disable JSON/structured output mode."""
        self.format_schema = None
        self.statusBar().showMessage("Format restrictions cleared")
    
    # ========== UI Event Handlers ==========
    
    def on_tools_toggled(self, state):
        """Handle tool calling checkbox toggle."""
        if state:
            self.enable_tools()
            self.update_features_status()
        else:
            self.disable_tools()
            self.update_features_status()
    
    def on_json_toggled(self, state):
        """Handle JSON mode checkbox toggle."""
        if state:
            # Enable simple JSON mode by default
            self.set_json_format()
            self.schema_button.setEnabled(True)
            self.update_features_status()
        else:
            self.clear_format()
            self.schema_button.setEnabled(False)
            self.update_features_status()
    
    def edit_json_schema(self):
        """Open dialog to edit JSON schema."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("JSON Schema Editor")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Define JSON schema for structured outputs:"))
        
        # Text editor for schema
        schema_edit = QTextEdit()
        schema_edit.setPlaceholderText('''{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer"}
  },
  "required": ["name"]
}''')
        
        # Pre-fill with current schema if it exists
        if hasattr(self, 'format_schema') and isinstance(self.format_schema, dict):
            import json
            schema_edit.setPlainText(json.dumps(self.format_schema, indent=2))
        
        layout.addWidget(schema_edit)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            # Parse and validate schema
            try:
                import json
                schema_text = schema_edit.toPlainText().strip()
                if schema_text:
                    schema = json.loads(schema_text)
                    self.set_json_format(schema)
                    self.statusBar().showMessage("Custom JSON schema applied")
                else:
                    # Empty = simple JSON mode
                    self.set_json_format()
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "Invalid JSON", f"Schema is not valid JSON:\\n{e}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to apply schema:\\n{e}")
    
    def update_features_status(self):
        """Update the features status label."""
        status_parts = []
        
        if hasattr(self, 'available_tools') and self.available_tools:
            status_parts.append(f"🛠️ {len(self.available_tools)} tools")
        
        if hasattr(self, 'format_schema') and self.format_schema:
            if isinstance(self.format_schema, dict):
                status_parts.append("📋 Custom schema")
            else:
                status_parts.append("📋 JSON mode")
        
        if status_parts:
            self.features_status.setText(" | ".join(status_parts))
            self.features_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.features_status.setText("No AI features active")
            self.features_status.setStyleSheet("color: gray; font-style: italic;")
    def show_loaded_models(self):
        """Show currently loaded models in memory."""
        result = self.client.list_running_models()
        
        if "error" in result:
            QMessageBox.warning(self, "Error", result["error"])
            return
        
        models = result.get("models", [])
        
        if not models:
            self.memory_status.setText("No models loaded")
            self.memory_status.setStyleSheet("color: gray;")
            QMessageBox.information(self, "Loaded Models", "No models currently in memory")
            return
        
        # Format model info for display
        info_lines = []
        total_size = 0
        for m in models:
            name = m.get("name", "Unknown")
            size = m.get("size", 0)
            size_vram = m.get("size_vram", 0)
            
            # Convert to MB
            size_mb = size / (1024 * 1024)
            vram_mb = size_vram / (1024 * 1024)
            total_size += size
            
            expires = m.get("expires_at", "")
            info_lines.append(f" {name}\n  RAM: {size_mb:.1f} MB | VRAM: {vram_mb:.1f} MB")
            if expires:
                info_lines.append(f"  Expires: {expires}")
        
        # Update status label
        total_mb = total_size / (1024 * 1024)
        self.memory_status.setText(f"{len(models)} model(s) loaded ({total_mb:.1f} MB)")
        self.memory_status.setStyleSheet("color: blue; font-weight: bold;")
        
        # Show detailed info
        msg = "\n\n".join(info_lines)
        QMessageBox.information(self, "Loaded Models", msg)
    
    def unload_current_model(self):
        """Unload the current model from memory."""
        model_name = self.model_combo.currentText()
        
        reply = QMessageBox.question(
            self, 
            "Unload Model", 
            f"Unload '{model_name}' from memory?\n\nThis will free up RAM/VRAM immediately.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.client.unload_model(model_name):
                self.memory_status.setText(f"Unloaded {model_name}")
                self.memory_status.setStyleSheet("color: green;")
                self.statusBar().showMessage(f"Model {model_name} unloaded from memory")
            else:
                QMessageBox.warning(self, "Error", f"Failed to unload {model_name}")
    
    def on_vram_monitoring_toggled(self, state):
        """Handle VRAM monitoring checkbox toggle."""
        import asyncio
        
        if state:
            # Start monitoring
            self.vram_monitoring_enabled = True
            # Use asyncio to start the monitoring session
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Start monitoring in background
            loop.create_task(self.start_vram_monitoring())
            self.statusBar().showMessage("Real-time VRAM monitoring started")
        else:
            # Stop monitoring
            self.vram_monitoring_enabled = False
            if self.vram_monitoring_session:
                # Schedule stop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.create_task(self.stop_vram_monitoring())
            self.vram_live_label.setText("VRAM: --")
            self.vram_live_label.setStyleSheet("color: gray;")
            self.statusBar().showMessage("Real-time VRAM monitoring stopped")
    
    async def start_vram_monitoring(self):
        """Start the VRAM monitoring session."""
        if self.vram_monitoring_session:
            await self.vram_monitoring_session.stop()
        
        # Create new session with custom thresholds
        thresholds = VRAMThresholds(
            warning_percent=75.0,   # Warning at 75%
            critical_percent=85.0,  # Critical at 85%
            oom_buffer_mb=256.0     # 256MB safety buffer
        )
        
        self.vram_monitoring_session = VRAMMonitoringSession(
            poll_interval=1.0,  # Update every second
            thresholds=thresholds,
            callback=self.on_vram_snapshot
        )
        
        await self.vram_monitoring_session.start()
    
    async def stop_vram_monitoring(self):
        """Stop the VRAM monitoring session."""
        if self.vram_monitoring_session:
            await self.vram_monitoring_session.stop()
            self.vram_monitoring_session = None
    
    def on_vram_snapshot(self, snapshot):
        """Update UI with latest VRAM snapshot."""
        # Update live label with current usage
        used_gb = snapshot.used_mb / 1024
        total_gb = snapshot.total_mb / 1024
        
        # Color code based on usage
        if snapshot.used_percent >= 85.0:
            color = "#FF3333"  # Red - Critical
        elif snapshot.used_percent >= 75.0:
            color = "#FFAA00"  # Orange - Warning
        else:
            color = "#00AA00"  # Green - OK
        
        self.vram_live_label.setText(
            f"VRAM: {used_gb:.2f}/{total_gb:.2f} GB ({snapshot.used_percent:.1f}%)"
        )
        self.vram_live_label.setStyleSheet(f"color: {color}; font-weight: bold;")
