"""Main Chat Window - Minimal PySide6 UI for AuraNexus."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QTextCursor
from typing import Optional
import sys


class ChatDisplayWidget(QFrame):
    """Custom widget to display chat messages."""
    
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Scroll area for messages
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        # Container for messages
        self.message_container = QWidget()
        self.message_layout = QVBoxLayout()
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(8)
        self.message_container.setLayout(self.message_layout)
        
        self.scroll.setWidget(self.message_container)
        layout.addWidget(self.scroll)
        self.setLayout(layout)
    
    def add_user_message(self, text: str) -> None:
        """Add a user message to the display."""
        label = QLabel(f"You: {text}")
        label.setWordWrap(True)
        label.setFont(QFont("Arial", 10))
        label.setStyleSheet("color: #0066cc; padding: 5px;")
        self.message_layout.addWidget(label)
        self.scroll_to_bottom()
    
    def add_assistant_message(self, text: str) -> None:
        """Add an assistant message to the display."""
        label = QLabel(f"Assistant: {text}")
        label.setWordWrap(True)
        label.setFont(QFont("Arial", 10))
        label.setStyleSheet("color: #228b22; padding: 5px;")
        self.message_layout.addWidget(label)
        self.scroll_to_bottom()
    
    def add_system_message(self, text: str) -> None:
        """Add a system message to the display."""
        label = QLabel(f"[System] {text}")
        label.setWordWrap(True)
        label.setFont(QFont("Arial", 9, QFont.Bold))
        label.setStyleSheet("color: #666666; padding: 5px;")
        self.message_layout.addWidget(label)
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the message display."""
        self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        )
    
    def clear_messages(self) -> None:
        """Clear all messages."""
        while self.message_layout.count():
            child = self.message_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


class ChatWorker(QThread):
    """Worker thread for LLM inference to avoid blocking UI."""
    
    response_ready = Signal(str)
    error_occurred = Signal(str)
    finished_inference = Signal()
    
    def __init__(self, llm_manager, messages: list):
        super().__init__()
        self.llm_manager = llm_manager
        self.messages = messages
    
    def run(self):
        """Run inference in background thread."""
        try:
            response = self.llm_manager.chat(self.messages, max_tokens=512)
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished_inference.emit()


class ChatWindow(QMainWindow):
    """Main chat application window."""
    
    def __init__(self, llm_manager, conversation_manager):
        super().__init__()
        self.llm_manager = llm_manager
        self.conversation_manager = conversation_manager
        self.chat_worker: Optional[ChatWorker] = None
        
        self.setWindowTitle("AuraNexus - AI Chat")
        self.setGeometry(100, 100, 900, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("AuraNexus Chat")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Chat display
        self.chat_display = ChatDisplayWidget()
        layout.addWidget(self.chat_display)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 9))
        self.status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.status_label)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(60)
        self.input_field.setFont(QFont("Arial", 10))
        self.input_field.setPlaceholderText("Type your message and press Ctrl+Enter to send...")
        input_layout.addWidget(self.input_field)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setMaximumWidth(100)
        self.send_button.setMinimumHeight(60)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        main_widget.setLayout(layout)
        
        # Show initial message
        self.chat_display.add_system_message("Model loaded. Start chatting!")
        
        # Keyboard shortcut: Ctrl+Enter to send
        self.input_field.keyPressEvent = self._input_key_press
    
    def _input_key_press(self, event):
        """Handle key press in input field."""
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self.send_message()
        else:
            QTextEdit.keyPressEvent(self.input_field, event)
    
    def send_message(self) -> None:
        """Send a message and get a response."""
        user_input = self.input_field.toPlainText().strip()
        
        if not user_input:
            return
        
        if not self.llm_manager.is_loaded():
            self.chat_display.add_system_message("Error: Model not loaded!")
            return
        
        # Clear input and disable button
        self.input_field.clear()
        self.send_button.setEnabled(False)
        self.status_label.setText("Generating response...")
        
        # Add user message to display and conversation
        self.chat_display.add_user_message(user_input)
        self.conversation_manager.add_message("user", user_input)
        
        # Get messages for API
        messages = self.conversation_manager.get_messages_for_api()
        
        # Start worker thread
        self.chat_worker = ChatWorker(self.llm_manager, messages)
        self.chat_worker.response_ready.connect(self.on_response_ready)
        self.chat_worker.error_occurred.connect(self.on_error)
        self.chat_worker.finished_inference.connect(self.on_inference_finished)
        self.chat_worker.start()
    
    def on_response_ready(self, response: str) -> None:
        """Handle response from LLM."""
        self.chat_display.add_assistant_message(response)
        self.conversation_manager.add_message("assistant", response)
    
    def on_error(self, error: str) -> None:
        """Handle error from LLM."""
        self.chat_display.add_system_message(f"Error: {error}")
    
    def on_inference_finished(self) -> None:
        """Handle inference completion."""
        self.send_button.setEnabled(True)
        self.status_label.setText("Ready")
    
    def closeEvent(self, event):
        """Save conversation before closing."""
        self.conversation_manager.save_conversation()
        event.accept()
