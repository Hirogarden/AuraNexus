"""AuraNexus Unified Chat Window

Modern Discord/Telegram-style interface with sidebar navigation.
Supports multiple modes: Chatbot, Storyteller, and Assistant.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLineEdit, QLabel, QComboBox, QGroupBox, 
    QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QColor
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from datetime import datetime

from secure_inference_engine import SecureInferenceEngine


class SecureChatWorker(QThread):
    """Worker thread for secure inference to avoid blocking UI."""
    
    finished = Signal(dict)
    error = Signal(str)
    chunk = Signal(str)
    
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
            if not self.engine.model or self.engine.loaded_model_path != self.model_name:
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
            
            self.finished.emit({
                "role": "assistant",
                "content": response_text,
                "model": self.model_name
            })
            
        except Exception as e:
            self.error.emit(str(e))


class UnifiedChatWindow(QMainWindow):
    """Main unified chat window with sidebar navigation."""
    
    # Project configurations
    PROJECTS = {
        "chatbot": {
            "name": "AI Chatbot",
            "icon": "💬",
            "system_prompt": "You are Aura, a friendly and helpful AI assistant. Provide clear, concise answers and be supportive.",
            "color": "#5865F2"  # Discord blurple
        },
        "storyteller": {
            "name": "Storyteller",
            "icon": "📖",
            "system_prompt": "You are an interactive storyteller creating immersive narrative experiences. Describe scenes vividly, respond to player actions creatively, and maintain story continuity. Format: Describe the scene, then present choices or ask what the player does.",
            "color": "#57F287"  # Green
        },
        "assistant": {
            "name": "AI Assistant",
            "icon": "🤖",
            "system_prompt": "You are a professional AI assistant focused on productivity and task completion. Provide detailed, actionable advice. Help with research, writing, coding, and problem-solving.",
            "color": "#FEE75C"  # Yellow
        }
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuraNexus - Unified Chat")
        self.resize(1400, 800)
        
        # Initialize secure inference engine
        self.engine = SecureInferenceEngine(verbose=True)
        
        # State management
        self.current_project = "chatbot"
        self.conversations: Dict[str, List[Dict[str, str]]] = {
            "chatbot": [],
            "storyteller": [],
            "assistant": []
        }
        self.current_model: Optional[Path] = None
        self.worker: Optional[SecureChatWorker] = None
        self.current_response = ""
        
        # Performance tracking
        self.last_inference_time: float = 0.0
        self.model_health_status: str = "Unknown"
        
        # Model management
        self.models_dir = Path(__file__).parent.parent / "engines" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize UI
        self._init_ui()
        self._scan_models()
    
    def _init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === LEFT SIDEBAR (Project Navigation) ===
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # === CENTER + RIGHT (Chat + Settings) ===
        splitter = QSplitter(Qt.Horizontal)
        
        # Center: Chat area
        chat_widget = self._create_chat_area()
        splitter.addWidget(chat_widget)
        
        # Right: Settings panel (collapsible)
        self.settings_container = QWidget()
        settings_container_layout = QVBoxLayout(self.settings_container)
        settings_container_layout.setContentsMargins(0, 0, 0, 0)
        settings_container_layout.setSpacing(0)
        
        # Toggle button
        self.settings_toggle_btn = QPushButton("⚙ Settings")
        self.settings_toggle_btn.setCheckable(True)
        self.settings_toggle_btn.setChecked(True)
        self.settings_toggle_btn.setFixedHeight(40)
        self.settings_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
            QPushButton:checked {
                background-color: #3C45A5;
            }
        """)
        self.settings_toggle_btn.clicked.connect(self._toggle_settings_panel)
        settings_container_layout.addWidget(self.settings_toggle_btn)
        
        # Settings panel
        self.settings_widget = self._create_settings_panel()
        settings_container_layout.addWidget(self.settings_widget)
        
        splitter.addWidget(self.settings_container)
        
        # Set initial sizes (70% chat, 30% settings)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter, stretch=1)
        
        # Status bar
        self.statusBar().showMessage("Ready - No model loaded")
    
    def _create_sidebar(self) -> QWidget:
        """Create the left sidebar with project navigation."""
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.StyledPanel)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2B2D31;
                border-right: 1px solid #1E1F22;
            }
        """)
        sidebar.setFixedWidth(200)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # App title
        title_label = QLabel("AuraNexus")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("color: #FFFFFF; padding: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Project buttons
        modes_label = QLabel("MODES")
        modes_label.setStyleSheet("color: #B5BAC1; font-size: 11px; padding: 5px;")
        layout.addWidget(modes_label)
        
        self.project_buttons = {}
        for project_id, config in self.PROJECTS.items():
            btn = QPushButton(f"{config['icon']}  {config['name']}")
            btn.setCheckable(True)
            btn.setChecked(project_id == self.current_project)
            btn.clicked.connect(lambda checked, p=project_id: self._switch_project(p))
            btn.setStyleSheet(self._get_project_button_style(project_id))
            btn.setMinimumHeight(40)
            layout.addWidget(btn)
            self.project_buttons[project_id] = btn
        
        layout.addStretch()
        
        # Clear conversation button
        clear_btn = QPushButton("🗑️  Clear Chat")
        clear_btn.clicked.connect(self._clear_current_chat)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ED4245;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C03537;
            }
        """)
        layout.addWidget(clear_btn)
        
        return sidebar
    
    def _get_project_button_style(self, project_id: str) -> str:
        """Get stylesheet for project button."""
        color = self.PROJECTS[project_id]['color']
        return f"""
            QPushButton {{
                background-color: #313338;
                color: #DBDEE1;
                border: none;
                border-radius: 4px;
                padding: 8px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #3A3C42;
            }}
            QPushButton:checked {{
                background-color: {color};
                color: #FFFFFF;
                font-weight: bold;
            }}
        """
    
    def _create_chat_area(self) -> QWidget:
        """Create the center chat conversation area."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Chat header (shows current project)
        self.chat_header = QLabel()
        self.chat_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.chat_header.setStyleSheet("padding: 15px; background-color: #313338; color: white;")
        self._update_chat_header()
        layout.addWidget(self.chat_header)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 10))
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #313338;
                color: #DBDEE1;
                border: none;
                padding: 10px;
            }
        """)
        layout.addWidget(self.chat_display, stretch=1)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #383A40;
                color: #DBDEE1;
                border: 1px solid #1E1F22;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
            }
        """)
        input_layout.addWidget(self.input_field, stretch=1)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
            QPushButton:disabled {
                background-color: #4E5058;
            }
        """)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        return widget
    
    def _create_settings_panel(self) -> QWidget:
        """Create the right settings panel."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #2B2D31; border: none;")
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # === Model Selection ===
        model_group = QGroupBox("Model Configuration")
        model_group.setStyleSheet("""
            QGroupBox {
                color: #DBDEE1;
                font-weight: bold;
                border: 1px solid #1E1F22;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        model_layout = QVBoxLayout()
        
        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #383A40;
                color: #DBDEE1;
                border: 1px solid #1E1F22;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        model_layout.addWidget(self.model_combo)
        
        model_btn_layout = QHBoxLayout()
        self.load_model_btn = QPushButton("Load")
        self.load_model_btn.clicked.connect(self._load_selected_model)
        model_btn_layout.addWidget(self.load_model_btn)
        
        self.browse_model_btn = QPushButton("Browse...")
        self.browse_model_btn.clicked.connect(self._browse_model)
        model_btn_layout.addWidget(self.browse_model_btn)
        
        self.rescan_model_btn = QPushButton("Rescan")
        self.rescan_model_btn.clicked.connect(self._rescan_models)
        model_btn_layout.addWidget(self.rescan_model_btn)
        
        self.health_check_btn = QPushButton("Test")
        self.health_check_btn.clicked.connect(self._test_model)
        model_btn_layout.addWidget(self.health_check_btn)
        
        model_layout.addLayout(model_btn_layout)
        
        # Context Size
        ctx_layout = QHBoxLayout()
        ctx_layout.addWidget(QLabel("Context Size:"))
        self.context_size_spin = QSpinBox()
        self.context_size_spin.setRange(512, 32768)
        self.context_size_spin.setSingleStep(512)
        self.context_size_spin.setValue(2048)
        self._style_spinbox(self.context_size_spin)
        ctx_layout.addWidget(self.context_size_spin)
        model_layout.addLayout(ctx_layout)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # === Sampling Parameters ===
        params_group = QGroupBox("Sampling Parameters")
        params_group.setStyleSheet(model_group.styleSheet())
        params_layout = QVBoxLayout()
        
        # Temperature
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self._style_spinbox(self.temperature_spin)
        temp_layout.addWidget(self.temperature_spin)
        params_layout.addLayout(temp_layout)
        
        # Top-P
        topp_layout = QHBoxLayout()
        topp_layout.addWidget(QLabel("Top-P:"))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(0.9)
        self._style_spinbox(self.top_p_spin)
        topp_layout.addWidget(self.top_p_spin)
        params_layout.addLayout(topp_layout)
        
        # Top-K
        topk_layout = QHBoxLayout()
        topk_layout.addWidget(QLabel("Top-K:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(0, 100)
        self.top_k_spin.setValue(40)
        self._style_spinbox(self.top_k_spin)
        topk_layout.addWidget(self.top_k_spin)
        params_layout.addLayout(topk_layout)
        
        # Max Tokens
        maxtoken_layout = QHBoxLayout()
        maxtoken_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 4096)
        self.max_tokens_spin.setValue(512)
        self._style_spinbox(self.max_tokens_spin)
        maxtoken_layout.addWidget(self.max_tokens_spin)
        params_layout.addLayout(maxtoken_layout)
        
        # Min-P
        minp_layout = QHBoxLayout()
        minp_layout.addWidget(QLabel("Min-P:"))
        self.min_p_spin = QDoubleSpinBox()
        self.min_p_spin.setRange(0.0, 1.0)
        self.min_p_spin.setSingleStep(0.05)
        self.min_p_spin.setValue(0.05)
        self._style_spinbox(self.min_p_spin)
        minp_layout.addWidget(self.min_p_spin)
        params_layout.addLayout(minp_layout)
        
        # Repeat Penalty
        repeat_layout = QHBoxLayout()
        repeat_layout.addWidget(QLabel("Repeat Penalty:"))
        self.repeat_penalty_spin = QDoubleSpinBox()
        self.repeat_penalty_spin.setRange(1.0, 2.0)
        self.repeat_penalty_spin.setSingleStep(0.05)
        self.repeat_penalty_spin.setValue(1.1)
        self._style_spinbox(self.repeat_penalty_spin)
        repeat_layout.addWidget(self.repeat_penalty_spin)
        params_layout.addLayout(repeat_layout)
        
        # Target Length
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target Sentences:"))
        self.target_length_spin = QSpinBox()
        self.target_length_spin.setRange(1, 20)
        self.target_length_spin.setValue(3)
        self.target_length_spin.setToolTip("Target number of sentences (auto-calculates max tokens)")
        self._style_spinbox(self.target_length_spin)
        target_layout.addWidget(self.target_length_spin)
        params_layout.addLayout(target_layout)
        
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # === Advanced Sampling ===
        advanced_group = QGroupBox("Advanced Sampling")
        advanced_group.setStyleSheet(model_group.styleSheet())
        advanced_layout = QVBoxLayout()
        
        self.dry_enabled = QCheckBox("DRY Sampling (Reduce Repetition)")
        self.dry_enabled.setStyleSheet("color: #DBDEE1;")
        advanced_layout.addWidget(self.dry_enabled)
        
        self.xtc_enabled = QCheckBox("XTC Sampling (Improve Creativity)")
        self.xtc_enabled.setStyleSheet("color: #DBDEE1;")
        advanced_layout.addWidget(self.xtc_enabled)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # === Story Settings (for Storyteller mode) ===
        story_group = QGroupBox("Story Settings")
        story_group.setStyleSheet(model_group.styleSheet())
        story_layout = QVBoxLayout()
        
        # Story Memory Length
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("Memory Length:"))
        self.story_memory_spin = QSpinBox()
        self.story_memory_spin.setRange(5, 50)
        self.story_memory_spin.setValue(20)
        self.story_memory_spin.setToolTip("Number of recent turns to remember")
        self._style_spinbox(self.story_memory_spin)
        memory_layout.addWidget(self.story_memory_spin)
        story_layout.addLayout(memory_layout)
        
        # Save/Load Story
        story_btn_layout = QHBoxLayout()
        self.save_story_btn = QPushButton("Save Story")
        self.save_story_btn.clicked.connect(self._save_story)
        story_btn_layout.addWidget(self.save_story_btn)
        
        self.load_story_btn = QPushButton("Load Story")
        self.load_story_btn.clicked.connect(self._load_story)
        story_btn_layout.addWidget(self.load_story_btn)
        story_layout.addLayout(story_btn_layout)
        
        story_group.setLayout(story_layout)
        layout.addWidget(story_group)
        
        # === RAG Settings (Placeholder) ===
        rag_group = QGroupBox("RAG Settings")
        rag_group.setStyleSheet(model_group.styleSheet())
        rag_layout = QVBoxLayout()
        
        rag_label = QLabel("RAG features coming soon...")
        rag_label.setStyleSheet("color: #B5BAC1; font-style: italic;")
        rag_layout.addWidget(rag_label)
        
        rag_group.setLayout(rag_layout)
        layout.addWidget(rag_group)
        
        layout.addStretch()
        
        scroll.setWidget(widget)
        return scroll
    
    def _style_spinbox(self, spinbox):
        """Apply consistent styling to spinboxes."""
        spinbox.setStyleSheet("""
            QSpinBox, QDoubleSpinBox {
                background-color: #383A40;
                color: #DBDEE1;
                border: 1px solid #1E1F22;
                border-radius: 4px;
                padding: 3px;
            }
        """)
    
    def _scan_models(self):
        """Scan models directory for GGUF files."""
        self.model_combo.clear()
        
        if not self.models_dir.exists():
            self.model_combo.addItem("(No models found)")
            return
        
        gguf_files = list(self.models_dir.glob("*.gguf"))
        
        if not gguf_files:
            self.model_combo.addItem("(No models found)")
            return
        
        for model_file in sorted(gguf_files):
            self.model_combo.addItem(model_file.name, model_file)
        
        self.statusBar().showMessage(f"Found {len(gguf_files)} model(s)")
    
    def _switch_project(self, project_id: str):
        """Switch to a different project/mode."""
        if project_id == self.current_project:
            return
        
        # Update button states
        for pid, btn in self.project_buttons.items():
            btn.setChecked(pid == project_id)
        
        self.current_project = project_id
        
        # Update UI
        self._update_chat_header()
        self._reload_conversation()
        
        self.statusBar().showMessage(f"Switched to {self.PROJECTS[project_id]['name']}")
    
    def _update_chat_header(self):
        """Update the chat header to show current project."""
        config = self.PROJECTS[self.current_project]
        self.chat_header.setText(f"{config['icon']}  {config['name']}")
    
    def _reload_conversation(self):
        """Reload the conversation for the current project."""
        self.chat_display.clear()
        
        messages = self.conversations[self.current_project]
        for msg in messages:
            role = "You" if msg["role"] == "user" else "Aura"
            self._append_message(role, msg["content"], from_history=True)
    
    def _load_selected_model(self):
        """Load the currently selected model."""
        if self.model_combo.count() == 0 or self.model_combo.currentText() == "(No models found)":
            QMessageBox.warning(self, "No Models", "No models available to load.")
            return
        
        model_data = self.model_combo.currentData()
        if not model_data or not isinstance(model_data, Path):
            return
        
        self._load_model(model_data)
    
    def _browse_model(self):
        """Browse for a GGUF model file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GGUF Model",
            str(self.models_dir),
            "GGUF Models (*.gguf);;All Files (*.*)"
        )
        
        if file_path:
            self._load_model(Path(file_path))
    
    def _load_model(self, model_path: Path):
        """Load a model into the inference engine."""
        self.statusBar().showMessage(f"Loading {model_path.name}...")
        self.load_model_btn.setEnabled(False)
        
        try:
            success, message = self.engine.load_model(str(model_path))
            
            if success:
                self.current_model = model_path
                self.model_health_status = "OK"
                self.statusBar().showMessage(f"Ready - {model_path.name} | Health: OK")
                self._append_system_message(f"Model loaded: {model_path.name}")
            else:
                self.statusBar().showMessage("Failed to load model")
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
        
        # Append user message
        self._append_message("You", user_input)
        self.input_field.clear()
        
        # Add to conversation history
        self.conversations[self.current_project].append({
            "role": "user",
            "content": user_input
        })
        
        # Prepare messages with system prompt
        config = self.PROJECTS[self.current_project]
        full_messages = [{"role": "system", "content": config["system_prompt"]}]
        
        # Use trimmed messages for storyteller mode
        trimmed_messages = self._get_trimmed_messages()
        full_messages.extend(trimmed_messages)
        
        # Calculate smart max_tokens based on target length
        target_sentences = self.target_length_spin.value()
        # Estimate ~150 tokens per sentence + 50% buffer to prevent cutoffs
        smart_max_tokens = int(target_sentences * 150 * 1.5)
        # Ensure minimum of 256 tokens
        smart_max_tokens = max(smart_max_tokens, 256)
        
        # Collect sampling parameters
        kwargs = {
            "temperature": self.temperature_spin.value(),
            "top_k": self.top_k_spin.value(),
            "top_p": self.top_p_spin.value(),
            "min_p": self.min_p_spin.value(),
            "max_tokens": smart_max_tokens,
            "repeat_penalty": self.repeat_penalty_spin.value(),
        }
        
        if self.dry_enabled.isChecked():
            kwargs["dry_multiplier"] = 0.8
            kwargs["dry_base"] = 1.75
        
        if self.xtc_enabled.isChecked():
            kwargs["xtc_probability"] = 0.1
            kwargs["xtc_threshold"] = 0.1
        
        # Start worker
        self.current_response = ""
        self._append_message("Aura", "")
        
        self.worker = SecureChatWorker(
            self.engine,
            full_messages,
            str(self.current_model),
            **kwargs
        )
        self.worker.chunk.connect(self._on_response_chunk)
        self.worker.finished.connect(self._on_response_finished)
        self.worker.error.connect(self._on_response_error)
        
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        
        # Track inference time
        import time
        self._inference_start_time = time.time()
        self.statusBar().showMessage("Generating...")
        
        self.worker.start()
    
    def _on_response_chunk(self, chunk: str):
        """Handle streaming response chunks."""
        self.current_response += chunk
        
        # Update last message
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertHtml(f"<b style='color: #00D9FF;'>Aura:</b> {self._format_message_html(self.current_response)}<br>")
        
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def _on_response_finished(self, response: Dict[str, Any]):
        """Handle complete response."""
        self.conversations[self.current_project].append(response)
        
        # Calculate latency
        import time
        if hasattr(self, '_inference_start_time'):
            latency = time.time() - self._inference_start_time
            self.last_inference_time = latency
            model_name = self.current_model.name if self.current_model else "Unknown"
            self.statusBar().showMessage(f"Ready - {model_name} | Latency: {latency:.2f}s")
        else:
            self.statusBar().showMessage("Ready")
        
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        
        self.current_response = ""
    
    def _on_response_error(self, error: str):
        """Handle inference error."""
        self._append_system_message(f"Error: {error}")
        
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.statusBar().showMessage("Error occurred")
    
    def _append_message(self, sender: str, content: str, from_history: bool = False):
        """Append a message to the chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        sender_color = "#00D9FF" if sender == "Aura" else "#57F287"
        formatted = self._format_message_html(content)
        cursor.insertHtml(f"<b style='color: {sender_color};'>{sender}:</b> {formatted}<br>")
        
        self.chat_display.setTextCursor(cursor)
        if not from_history:
            self.chat_display.ensureCursorVisible()
    
    def _append_system_message(self, content: str):
        """Append a system message to the chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(f"<i style='color: #B5BAC1;'>[System: {content}]</i><br>")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def _format_message_html(self, content: str) -> str:
        """Format message content for HTML display."""
        content = content.replace("&", "&amp;")
        content = content.replace("<", "&lt;")
        content = content.replace(">", "&gt;")
        content = content.replace("\n", "<br>")
        return content
    
    def _clear_current_chat(self):
        """Clear the current project's conversation."""
        reply = QMessageBox.question(
            self,
            "Clear Chat",
            f"Clear conversation for {self.PROJECTS[self.current_project]['name']}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.conversations[self.current_project].clear()
            self.chat_display.clear()
            self._append_system_message("Conversation cleared")
    
    def _save_story(self):
        """Save current story/conversation to JSON file."""
        if not self.conversations[self.current_project]:
            QMessageBox.warning(self, "No Story", "No story to save!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Story",
            f"./{self.current_project}_story.json",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                story_data = {
                    "project": self.current_project,
                    "system_prompt": self.PROJECTS[self.current_project]["system_prompt"],
                    "messages": self.conversations[self.current_project],
                    "settings": {
                        "temperature": self.temperature_spin.value(),
                        "top_k": self.top_k_spin.value(),
                        "top_p": self.top_p_spin.value(),
                        "min_p": self.min_p_spin.value(),
                        "max_tokens": self.max_tokens_spin.value(),
                        "repeat_penalty": self.repeat_penalty_spin.value(),
                        "story_memory": self.story_memory_spin.value(),
                    }
                }
                
                with open(file_path, 'w') as f:
                    json.dump(story_data, f, indent=2)
                
                self.statusBar().showMessage(f"Story saved to {file_path}")
                self._append_system_message(f"Story saved successfully")
                
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save story:\n{str(e)}")
    
    def _load_story(self):
        """Load story/conversation from JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Story",
            "./",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    story_data = json.load(f)
                
                # Validate story data
                if "messages" not in story_data:
                    raise ValueError("Invalid story file format")
                
                # Switch to appropriate project if different
                if "project" in story_data and story_data["project"] != self.current_project:
                    self._switch_project(story_data["project"])
                
                # Load messages
                self.conversations[self.current_project] = story_data["messages"]
                
                # Load settings if available
                if "settings" in story_data:
                    settings = story_data["settings"]
                    self.temperature_spin.setValue(settings.get("temperature", 0.7))
                    self.top_k_spin.setValue(settings.get("top_k", 40))
                    self.top_p_spin.setValue(settings.get("top_p", 0.9))
                    self.min_p_spin.setValue(settings.get("min_p", 0.05))
                    self.max_tokens_spin.setValue(settings.get("max_tokens", 512))
                    self.repeat_penalty_spin.setValue(settings.get("repeat_penalty", 1.1))
                    self.story_memory_spin.setValue(settings.get("story_memory", 20))
                
                # Reload display
                self._reload_conversation()
                
                self.statusBar().showMessage(f"Story loaded from {file_path}")
                self._append_system_message("Story loaded successfully")
                
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load story:\n{str(e)}")
    
    def _get_trimmed_messages(self) -> List[Dict[str, str]]:
        """Get conversation messages trimmed to story memory length."""
        messages = self.conversations[self.current_project]
        memory_length = self.story_memory_spin.value()
        
        # For storyteller mode, respect memory setting
        if self.current_project == "storyteller" and len(messages) > memory_length * 2:
            # Keep system message + last N exchanges (user + assistant pairs)
            trimmed = messages[-(memory_length * 2):]
            return trimmed
        
        return messages
    
    def _toggle_settings_panel(self):
        """Toggle visibility of settings panel."""
        is_visible = self.settings_toggle_btn.isChecked()
        self.settings_widget.setVisible(is_visible)
        if is_visible:
            self.settings_toggle_btn.setText("⚙ Settings")
        else:
            self.settings_toggle_btn.setText("⚙ Show Settings")
    
    def _browse_model(self):
        """Browse for a model file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GGUF Model",
            str(self.models_dir),
            "GGUF Models (*.gguf);;All Files (*.*)"
        )
        
        if file_path:
            model_path = Path(file_path)
            # Add to combo if not already there
            if self.model_combo.findText(model_path.name) == -1:
                self.model_combo.addItem(model_path.name, model_path)
            self.model_combo.setCurrentText(model_path.name)
            self._load_selected_model()
    
    def _rescan_models(self):
        """Rescan the models directory for GGUF files."""
        self.statusBar().showMessage("Scanning for models...")
        
        # Clear existing items
        self.model_combo.clear()
        
        # Scan for .gguf files
        model_files = list(self.models_dir.glob("*.gguf"))
        
        if model_files:
            for model_file in sorted(model_files):
                self.model_combo.addItem(model_file.name, model_file)
            self.statusBar().showMessage(f"Found {len(model_files)} model(s)")
            self._append_system_message(f"Scanned models directory: found {len(model_files)} GGUF file(s)")
        else:
            self.statusBar().showMessage(f"No models found in {self.models_dir}")
            self._append_system_message(f"No .gguf files found in {self.models_dir}")
    
    def _test_model(self):
        """Test the currently loaded model with a simple prompt."""
        if not self.current_model or not self.engine:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return
        
        # Disable UI
        self.health_check_btn.setEnabled(False)
        self.statusBar().showMessage("Testing model...")
        
        # Simple test prompt
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'OK' if you can read this."}
        ]
        
        try:
            import time
            start_time = time.time()
            
            response = self.engine.chat(
                test_messages,
                temperature=0.7,
                max_tokens=32,
                top_k=40,
                top_p=0.95,
                min_p=0.05
            )
            
            latency = time.time() - start_time
            
            if response and response.get("content"):
                self.model_health_status = "OK"
                self.last_inference_time = latency
                model_name = self.current_model.name if self.current_model else "Unknown"
                self.statusBar().showMessage(f"Ready - {model_name} | Health: OK | Test Latency: {latency:.2f}s")
                self._append_system_message(f"Model health check: OK (latency: {latency:.2f}s)")
            else:
                self.model_health_status = "Error"
                self.statusBar().showMessage("Model test failed - no response")
                self._append_system_message("Model health check: FAILED (no response)")
        
        except Exception as e:
            self.model_health_status = "Error"
            self.statusBar().showMessage(f"Model test failed: {str(e)}")
            self._append_system_message(f"Model health check: ERROR - {str(e)}")
        
        finally:
            self.health_check_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.engine.model:
            self.engine.unload_model()
        event.accept()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = UnifiedChatWindow()
    window.show()
    sys.exit(app.exec())
