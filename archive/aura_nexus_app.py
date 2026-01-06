"""DEPRECATED: Full-featured Aura Nexus App (OLD VERSION)

⚠️  THIS FILE IS DEPRECATED - DO NOT USE AS MAIN LAUNCHER ⚠️

This was the complex full-featured app from the previous program version.
It has been replaced with the simpler chat_launcher.py / src/ollama_chat.py.

PRESERVED FOR CODE HARVESTING ONLY
Useful features to extract:
- Avatar integration (VSeeFace, Animaze, VTS)
- Service management tab
- AnythingLLM integration
- Model management UI
- Settings persistence
- Upgraded AsyncOllamaClient health checks

To use the CURRENT app, run:
    python chat_launcher.py
    OR
    run_aura_nexus.ps1
"""

import sys
import threading
import time
from dataclasses import dataclass
from typing import List, Dict, Optional
import asyncio
from pathlib import Path

# Add src to path for ollama_client import
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from ollama_client import AsyncOllamaClient, Message as OllamaMessage, ResponseError
except ImportError:
    # Fallback if imports fail
    AsyncOllamaClient = None
    OllamaMessage = None
    ResponseError = None

from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QCheckBox,
    QComboBox,
    QMessageBox,
    QLayout,
    QSizePolicy,
    QScrollArea,
    QFileDialog,
    QSpinBox,
    QProgressDialog,
    QInputDialog,
)


# Message dataclass now imported from ollama_client
# OllamaClient class replaced with AsyncOllamaClient import
# Legacy sync wrapper for backward compatibility
class OllamaClient:
    """Synchronous wrapper around AsyncOllamaClient for backward compatibility."""
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._async_client = None
        if AsyncOllamaClient:
            self._async_client = AsyncOllamaClient(host=base_url, model=model)
    
    def chat(self, messages: List, system_prompt: Optional[str] = None, options: Optional[Dict] = None, model: Optional[str] = None) -> str:
        """Synchronous chat method - runs async client in sync context."""
        if not self._async_client:
            return "[Error: AsyncOllamaClient not available]"
        
        # Convert Message objects if needed
        if AsyncOllamaClient and OllamaMessage:
            conv_msgs = []
            for m in messages:
                if hasattr(m, 'role') and hasattr(m, 'content'):
                    conv_msgs.append(OllamaMessage(role=m.role, content=m.content))
                else:
                    conv_msgs.append(m)
            
            # Run async method in sync context
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    response = loop.run_until_complete(
                        self._async_client.chat(
                            messages=conv_msgs,
                            model=model or self.model,
                            options=options
                        )
                    )
                    return response.get('message', {}).get('content', '')
                finally:
                    loop.close()
            except Exception as e:
                if ResponseError and isinstance(e, ResponseError):
                    return f"[Ollama error: {e.error} (HTTP {e.status_code})]"
                return f"[Error contacting Ollama: {e}]"
        return "[Error: Required imports not available]"


# Message dataclass for backward compatibility
@dataclass
class Message:
    role: str
    content: str


class LlamaCppClient:
    """Simple wrapper around llama-cpp-python to load a GGUF model and provide a
    chat() method similar to OllamaClient.
    """
    def __init__(self, model_path: str, n_ctx: int = 2048, n_threads: Optional[int] = None) -> None:
        try:
            from llama_cpp import Llama
        except Exception as e:
            raise RuntimeError("llama-cpp-python is not installed or failed to import") from e
        self.model_path = model_path
        self.n_ctx = n_ctx
        try:
            kwargs = {"model_path": model_path, "n_ctx": n_ctx}
            if n_threads:
                kwargs["n_threads"] = int(n_threads)
            self._llm = Llama(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to load GGUF model: {e}") from e

    def chat(self, messages: List[Message], system_prompt: Optional[str] = None, options: Optional[Dict] = None, model: Optional[str] = None) -> str:
        prompt = ""
        if system_prompt:
            prompt += system_prompt + "\n\n"
        for m in messages:
            # Keep a compact representation; the model cares about the text
            prompt += f"{m.role}: {m.content}\n"
        max_tokens = 512
        try:
            if options and isinstance(options, dict):
                if options.get("max_tokens"):
                    max_tokens = int(options.get("max_tokens"))
                elif options.get("num_predict"):
                    max_tokens = int(options.get("num_predict"))
        except Exception:
            pass
        try:
            resp = self._llm.create_completion(prompt=prompt, max_tokens=max_tokens, echo=False)
            # Response structure may vary; attempt to extract text
            text = ""
            try:
                choices = getattr(resp, 'choices', None) or resp.get('choices') if isinstance(resp, dict) else None
                if choices and len(choices) and isinstance(choices[0], dict):
                    text = choices[0].get('text', '')
                elif isinstance(resp, dict) and 'text' in resp:
                    text = resp.get('text', '')
                else:
                    text = str(resp)
            except Exception:
                text = str(resp)
            return text or ""
        except Exception as e:
            return f"[Error invoking local model: {e}]"

    def close(self) -> None:
        try:
            del self._llm
        except Exception:
            pass


class DummyTTS:
    def speak_async(self, text: str) -> None:
        return None
    def speaking(self) -> bool:
        return False


class Invoker(QObject):
    call = Signal(object)
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        try:
            self.call.connect(self._run)
        except Exception:
            pass
    def _run(self, fn) -> None:
        try:
            if callable(fn):
                fn()
        except Exception:
            pass


class ChatInput(QTextEdit):
    send = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._enter_sends = True
        try:
            self.setAcceptRichText(False)
        except Exception:
            pass

    def set_enter_sends(self, enabled: bool) -> None:
        self._enter_sends = bool(enabled)

    def keyPressEvent(self, event):  # type: ignore[override]
        try:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if mods & Qt.ControlModifier:
                    event.accept()
                    self.send.emit()
                    return
                if self._enter_sends and not (mods & (Qt.ShiftModifier | Qt.AltModifier)):
                    event.accept()
                    self.send.emit()
                    return
                event.accept()
                self.send.emit()
                return
        except Exception:
            pass
        return super().keyPressEvent(event)


class FileDropLineEdit(QLineEdit):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # type: ignore[override]
        try:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragEnterEvent(event)
        except Exception:
            super().dragEnterEvent(event)

    def dropEvent(self, event):  # type: ignore[override]
        try:
            urls = event.mimeData().urls()
            if urls:
                # Use first file only
                path = urls[0].toLocalFile()
                if path:
                    self.setText(path)
            else:
                super().dropEvent(event)
        except Exception:
            super().dropEvent(event)


class AuraNexusWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Aura Nexus")
        try:
            from PySide6.QtGui import QIcon
            import os
            here = os.path.dirname(os.path.abspath(__file__))
            assets = os.path.join(here, "assets")
            icon_path = None
            for cand in ("aura_nexus.ico", "aura_nexus.png"):
                p = os.path.join(assets, cand)
                if os.path.exists(p):
                    icon_path = p
                    break
            if icon_path:
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)

        self.ollama = OllamaClient()
        try:
            self.tts = TTS()
        except Exception:
            self.tts = DummyTTS()
        self._invoker = Invoker(self)
        self.local_llm_client = None
        self.local_model_enabled = False
        self.local_n_ctx = 2048
        self.local_n_threads = None
        self.local_num_predict = 512

        self.system_prompt = "You are Aura, a friendly, helpful AI assistant. Keep answers concise."
        self.messages: List[Message] = []
        self.speak_enabled = True
        self.anyllm_thread_id: Optional[str] = None
        self.anyllm_enabled_flag: bool = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        header = QGroupBox("Settings")
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        header_layout = QVBoxLayout(header)
        header_layout.setSizeConstraint(QLayout.SetMinimumSize)

        h1 = QHBoxLayout()
        h1.setSpacing(8)
        h1.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("llama3")
        h1.addWidget(self.model_combo)
        try:
            self.model_combo.currentIndexChanged.connect(lambda _: QTimer.singleShot(0, self._on_model_combo_changed))
        except Exception:
            pass
        self.model_refresh_btn = QPushButton("Refresh")
        self.model_refresh_btn.clicked.connect(self._refresh_models_dropdown_async)
        h1.addWidget(self.model_refresh_btn)
        self.model_health_btn = QPushButton("Health")
        self.model_health_btn.clicked.connect(self._update_llm_health_async)
        h1.addWidget(self.model_health_btn)
        self.model_test_btn = QPushButton("Test Chat")
        self.model_test_btn.clicked.connect(self.on_test_chat)
        h1.addWidget(self.model_test_btn)
        self.llm_health = QLabel("Unknown")
        self.llm_health.setStyleSheet("color: #666; font-weight: bold")
        h1.addWidget(QLabel("LLM"))
        h1.addWidget(self.llm_health)
        self.latency_label = QLabel("Latency: -")
        self.latency_label.setStyleSheet("color: #555")
        h1.addWidget(self.latency_label)
        h1.addStretch(1)
        header_layout.addLayout(h1)

        # Local GGUF model controls
        h1b = QHBoxLayout()
        h1b.setSpacing(8)
        self.local_model_chk = QCheckBox("Local GGUF")
        self.local_model_chk.stateChanged.connect(lambda _: self._on_toggle_local_model())
        h1b.addWidget(self.local_model_chk)
        self.local_model_path_edit = FileDropLineEdit()
        self.local_model_path_edit.setMinimumWidth(320)
        h1b.addWidget(self.local_model_path_edit, 1)
        self.local_model_browse_btn = QPushButton("Browse")
        self.local_model_browse_btn.clicked.connect(self._on_browse_local_model)
        h1b.addWidget(self.local_model_browse_btn)
        self.local_model_load_btn = QPushButton("Load")
        self.local_model_load_btn.clicked.connect(self._on_load_local_model)
        h1b.addWidget(self.local_model_load_btn)
        self.local_model_scan_btn = QPushButton("Scan")
        self.local_model_scan_btn.clicked.connect(self._on_scan_local_models)
        h1b.addWidget(self.local_model_scan_btn)
        self.local_model_import_btn = QPushButton("Import to Ollama")
        self.local_model_import_btn.clicked.connect(self._on_import_to_ollama)
        h1b.addWidget(self.local_model_import_btn)
        # Advanced model controls for local GGUF
        self._adv_model_layout = QHBoxLayout()
        self._adv_model_layout.setSpacing(8)
        self._n_ctx_spin = QSpinBox()
        self._n_ctx_spin.setRange(512, 32768)
        self._n_ctx_spin.setValue(self.local_n_ctx)
        self._adv_model_layout.addWidget(QLabel("n_ctx"))
        self._adv_model_layout.addWidget(self._n_ctx_spin)
        self._n_threads_spin = QSpinBox()
        self._n_threads_spin.setRange(1, 256)
        if self.local_n_threads:
            self._n_threads_spin.setValue(self.local_n_threads)
        self._adv_model_layout.addWidget(QLabel("threads"))
        self._adv_model_layout.addWidget(self._n_threads_spin)
        self._num_predict_spin = QSpinBox()
        self._num_predict_spin.setRange(16, 4096)
        self._num_predict_spin.setValue(self.local_num_predict)
        self._adv_model_layout.addWidget(QLabel("predict"))
        self._adv_model_layout.addWidget(self._num_predict_spin)
        header_layout.addLayout(self._adv_model_layout)
        header_layout.addLayout(h1b)

        h2 = QHBoxLayout()
        h2.setSpacing(8)
        h2.addWidget(QLabel("System Prompt"))
        self.system_edit = QLineEdit(self.system_prompt)
        self.system_edit.setMinimumWidth(240)
        h2.addWidget(self.system_edit, 1)
        h2.addWidget(QLabel("Assistant"))
        self.assistant_name_edit = QLineEdit("Aura")
        self.assistant_name_edit.setFixedWidth(110)
        h2.addWidget(self.assistant_name_edit)
        h2.addWidget(QLabel("User"))
        self.user_name_edit = QLineEdit("You")
        self.user_name_edit.setFixedWidth(90)
        h2.addWidget(self.user_name_edit)
        h2.addWidget(QLabel("Target Length"))
        self.response_target_spin = QSpinBox()
        self.response_target_spin.setRange(1, 20)
        self.response_target_spin.setValue(3)
        self.response_target_spin.setToolTip("Target sentences to aim for")
        h2.addWidget(self.response_target_spin)
        self.response_allow_overflow = QCheckBox("Allow overflow")
        self.response_allow_overflow.setChecked(True)
        h2.addWidget(self.response_allow_overflow)
        self.speak_toggle = QPushButton("Voice: On")
        self.speak_toggle.setCheckable(True)
        self.speak_toggle.setChecked(True)
        self.speak_toggle.clicked.connect(self.on_toggle_voice)
        h2.addWidget(self.speak_toggle)
        self.enter_send_chk = QCheckBox("Enter Sends")
        self.enter_send_chk.setChecked(True)
        self.enter_send_chk.stateChanged.connect(self.on_enter_sends_changed)
        h2.addWidget(self.enter_send_chk)
        self.auto_intro_chk = QCheckBox("Auto Intro")
        self.auto_intro_chk.setChecked(True)
        h2.addWidget(self.auto_intro_chk)
        header_layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.setSpacing(8)
        self.anyllm_enable = QCheckBox("AnythingLLM")
        self.anyllm_enable.setChecked(False)
        h3.addWidget(self.anyllm_enable)
        self.anyllm_mode = QComboBox()
        self.anyllm_mode.addItems(["Augment (RAG)", "Responder"])
        h3.addWidget(self.anyllm_mode)
        self.anyllm_base = QLineEdit("http://localhost:3001")
        self.anyllm_base.setFixedWidth(140)
        h3.addWidget(self.anyllm_base)
        self.anyllm_key = QLineEdit()
        self.anyllm_key.setEchoMode(QLineEdit.Password)
        self.anyllm_key.setPlaceholderText("API Key")
        self.anyllm_key.setFixedWidth(140)
        h3.addWidget(self.anyllm_key)
        self.anyllm_workspace = QLineEdit()
        self.anyllm_workspace.setPlaceholderText("Workspace")
        self.anyllm_workspace.setFixedWidth(120)
        h3.addWidget(self.anyllm_workspace)
        refresh_btn = QPushButton("Apply")
        refresh_btn.clicked.connect(self.on_apply_settings)
        h3.addWidget(refresh_btn)
        self.diag_btn = QPushButton("Diag")
        self.diag_btn.clicked.connect(self.on_run_diagnostics)
        h3.addWidget(self.diag_btn)
        h3.addStretch(1)
        header_layout.addLayout(h3)

        # AnythingLLM logging options (new line to avoid overflow)
        h3b = QHBoxLayout()
        self.anyllm_log_history = QCheckBox("Log chat history to AnythingLLM")
        self.anyllm_log_history.setChecked(False)
        h3b.addWidget(self.anyllm_log_history)
        h3b.addWidget(QLabel("Log As"))
        self.anyllm_log_target = QComboBox()
        self.anyllm_log_target.addItems(["Documents", "Chat History"])
        self.anyllm_log_target.setCurrentIndex(0)
        h3b.addWidget(self.anyllm_log_target)
        h3b.addStretch(1)
        header_layout.addLayout(h3b)

        h4 = QHBoxLayout()
        h4.setSpacing(8)
        h4.addWidget(QLabel("Avatar"))
        self.avatar_provider = QComboBox()
        self.avatar_provider.addItems(["None", "VSeeFace (3D)", "Animaze (2D/3D)", "OBS Face Tracker", "Custom WebSocket"])
        self.avatar_provider.setCurrentIndex(0)
        h4.addWidget(self.avatar_provider)
        h4.addWidget(QLabel("Type"))
        self.avatar_type = QComboBox()
        self.avatar_type.addItems(["2D", "3D"]) 
        self.avatar_type.setCurrentIndex(0)
        h4.addWidget(self.avatar_type)
        h4.addWidget(QLabel("Body"))
        self.avatar_body = QComboBox()
        self.avatar_body.addItems(["Head", "Upper Body", "Full Body"]) 
        self.avatar_body.setCurrentIndex(0)
        h4.addWidget(self.avatar_body)
        h4.addWidget(QLabel("Host"))
        self.avatar_host = QLineEdit("localhost")
        self.avatar_host.setFixedWidth(140)
        h4.addWidget(self.avatar_host)
        h4.addWidget(QLabel("Port"))
        self.avatar_port = QLineEdit("8001")
        self.avatar_port.setFixedWidth(80)
        h4.addWidget(self.avatar_port)
        self.avatar_connect_btn = QPushButton("Connect Avatar")
        self.avatar_connect_btn.clicked.connect(self.on_avatar_connect)
        h4.addWidget(self.avatar_connect_btn)
        self.avatar_test_btn = QPushButton("Test Avatar")
        self.avatar_test_btn.clicked.connect(self.on_avatar_test)
        h4.addWidget(self.avatar_test_btn)
        self.avatar_save_btn = QPushButton("Save Avatar")
        self.avatar_save_btn.setToolTip("Save avatar settings to your profile")
        self.avatar_save_btn.clicked.connect(self._save_avatar_profile)
        h4.addWidget(self.avatar_save_btn)
        h4.addStretch(1)
        header_layout.addLayout(h4)

        # Chat tab FIRST (was Settings previously) for direct user interaction
        chat_tab = QWidget()
        chat_v = QVBoxLayout(chat_tab)
        splitter = QSplitter()
        chat_v.addWidget(splitter, 1)
        left = QGroupBox("Avatar")
        lv = QVBoxLayout(left)
        self.avatar_label = QLabel("Avatar")
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setMinimumHeight(350)
        lv.addWidget(self.avatar_label, 1)
        self.idle_movie = None
        self.talk_movie = None
        self._set_avatar_state("idle")
        splitter.addWidget(left)
        right = QWidget()
        rv = QVBoxLayout(right)
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        rv.addWidget(self.chat_view, 1)
        input_row = QHBoxLayout()
        self.input_edit = ChatInput()
        self.input_edit.setMinimumHeight(72)
        try:
            self.input_edit.setPlaceholderText("Say something... (Shift+Enter newline, Ctrl+Enter send)")
        except Exception:
            pass
        self.input_edit.send.connect(self.on_send)
        new_chat_btn = QPushButton("New Chat")
        new_chat_btn.clicked.connect(self.on_new_chat)
        try:
            new_chat_btn.setShortcut(QKeySequence("Ctrl+N"))
        except Exception:
            pass
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.on_send)
        save_close_btn = QPushButton("Save & Close")
        save_close_btn.setToolTip("Save chat (if enabled) to selected AnythingLLM target and exit")
        save_close_btn.clicked.connect(self.on_save_and_close)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(new_chat_btn)
        input_row.addWidget(save_close_btn)
        input_row.addWidget(send_btn)
        rv.addLayout(input_row)
        splitter.addWidget(right)
        splitter.setSizes([450, 650])
        tabs.addTab(chat_tab, "Chat")

        services_tab = QWidget()
        sv = QVBoxLayout(services_tab)
        sv.setSpacing(10)
        sv.addWidget(QLabel("Services"))
        svc_box = QGroupBox("Local Runtimes & Integrations")
        svc_l = QVBoxLayout(svc_box)
        # Ollama status row
        oll_row = QHBoxLayout()
        oll_row.addWidget(QLabel("Ollama"))
        self.ollama_status = QLabel("Unknown")
        self.ollama_status.setStyleSheet("color: #666; font-weight: bold")
        oll_row.addWidget(self.ollama_status)
        btn_check_oll = QPushButton("Check")
        btn_check_oll.clicked.connect(self._update_llm_health_async)
        oll_row.addWidget(btn_check_oll)
        btn_start_oll = QPushButton("Start")
        btn_start_oll.clicked.connect(self._start_ollama_async)
        oll_row.addWidget(btn_start_oll)
        btn_open_oll = QPushButton("Open UI")
        btn_open_oll.clicked.connect(lambda: self._open_url("http://localhost:11434"))
        oll_row.addWidget(btn_open_oll)
        oll_row.addStretch(1)
        svc_l.addLayout(oll_row)

        # Docker Desktop row
        dock_row = QHBoxLayout()
        dock_row.addWidget(QLabel("Docker Desktop"))
        self.docker_status = QLabel("Unknown")
        self.docker_status.setStyleSheet("color: #666; font-weight: bold")
        dock_row.addWidget(self.docker_status)
        btn_check_dock = QPushButton("Check")
        btn_check_dock.clicked.connect(self.on_check_dependencies)
        dock_row.addWidget(btn_check_dock)
        btn_start_dock = QPushButton("Start")
        btn_start_dock.clicked.connect(lambda: threading.Thread(target=self._force_connect_work, daemon=True).start())
        dock_row.addWidget(btn_start_dock)
        dock_row.addStretch(1)
        svc_l.addLayout(dock_row)

        # AnythingLLM status row
        any_row = QHBoxLayout()
        any_row.addWidget(QLabel("AnythingLLM"))
        self.anyllm_status = QLabel("Unknown")
        self.anyllm_status.setStyleSheet("color: #666; font-weight: bold")
        any_row.addWidget(self.anyllm_status)
        btn_check_any = QPushButton("Check")
        btn_check_any.clicked.connect(self._probe_anyllm)
        any_row.addWidget(btn_check_any)
        btn_open_any = QPushButton("Open UI")
        btn_open_any.clicked.connect(lambda: self._open_url(self.anyllm_base.text().strip() or "http://localhost:3001"))
        any_row.addWidget(btn_open_any)
        any_row.addStretch(1)
        svc_l.addLayout(any_row)

        # GPU row
        gpu_row = QHBoxLayout()
        gpu_row.addWidget(QLabel("GPU (NVIDIA)"))
        self.gpu_status = QLabel("Unknown")
        self.gpu_status.setStyleSheet("color: #666; font-weight: bold")
        gpu_row.addWidget(self.gpu_status)
        btn_check_gpu = QPushButton("Check")
        btn_check_gpu.clicked.connect(lambda: self._update_gpu_status())
        gpu_row.addWidget(btn_check_gpu)
        gpu_row.addStretch(1)
        svc_l.addLayout(gpu_row)

        sv.addWidget(svc_box)

        # Console
        self.services_console = QTextEdit()
        self.services_console.setReadOnly(True)
        self.services_console.setPlaceholderText("Service logs will appear here (checks, starts, health updates).")
        sv.addWidget(self.services_console, 1)
        tabs.addTab(services_tab, "Services")

        models_tab = QWidget()
        mv = QVBoxLayout(models_tab)
        mv.addWidget(QLabel("Models (Local Runtimes)"))
        self.models_status = QLabel("Detecting providers...")
        mv.addWidget(self.models_status)
        oll_box = QGroupBox("Ollama")
        ollv = QHBoxLayout(oll_box)
        self.oll_detect_label = QLabel("Unknown")
        self.oll_model_input = QLineEdit("llama3")
        oll_pull_btn = QPushButton("Pull Model")
        oll_pull_btn.clicked.connect(self.on_ollama_pull)
        oll_list_btn = QPushButton("List Models")
        oll_list_btn.clicked.connect(self.on_ollama_list)
        for w in (QLabel("Status"), self.oll_detect_label, QLabel("Model"), self.oll_model_input, oll_pull_btn, oll_list_btn):
            ollv.addWidget(w)
        mv.addWidget(oll_box)
        self.models_console = QTextEdit()
        self.models_console.setReadOnly(True)
        mv.addWidget(self.models_console, 1)
        tabs.addTab(models_tab, "Models")

        # Settings tab LAST now
        settings_tab = QWidget()
        settings_v = QVBoxLayout(settings_tab)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        try:
            settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        settings_scroll.setWidget(header)
        settings_v.addWidget(settings_scroll)
        tabs.addTab(settings_tab, "Settings")

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_left = QLabel("Ready")
        status.addWidget(self.status_left)
        dep_btn = QPushButton("Check Dependencies")
        dep_btn.clicked.connect(self.on_check_dependencies)
        status.addPermanentWidget(dep_btn)
        force_btn = QPushButton("Connect Services")
        force_btn.clicked.connect(self.on_force_connect)
        status.addPermanentWidget(force_btn)
        self.brevity_toggle = QPushButton("Brevity: On")
        self.brevity_toggle.setCheckable(True)
        self.brevity_toggle.setChecked(True)
        self.brevity_toggle.clicked.connect(self.on_toggle_brevity)
        status.addPermanentWidget(self.brevity_toggle)

        self.talk_timer = QTimer(self)
        self.talk_timer.setInterval(150)
        self.talk_timer.timeout.connect(self._poll_talking)
        self.talk_timer.start()

        try:
            self.shortcut_new_chat = QShortcut(QKeySequence("Ctrl+N"), self)
            self.shortcut_new_chat.activated.connect(self.on_new_chat)
        except Exception:
            pass

        QTimer.singleShot(0, self.on_check_dependencies_async)
        QTimer.singleShot(0, self._detect_providers_async)
        QTimer.singleShot(0, self._refresh_models_dropdown_async)
        QTimer.singleShot(0, self._migrate_legacy_profile_once)
        QTimer.singleShot(0, self._load_profile)
        QTimer.singleShot(0, self._load_avatar_profile)
        QTimer.singleShot(250, self._update_llm_health_async)
        self._last_llm_health_ts = 0.0
        self._last_llm_health_status = None
        self._last_llm_health_detail = None
        self._auto_intro_done = False
        QTimer.singleShot(800, self._auto_intro_if_needed)
        self._vts = None

    def _profile_path(self) -> str:
        import os
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AuraNexus")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        return os.path.join(base, "profile.json")

    def _legacy_profile_path(self) -> str:
        # Legacy migration has been removed; keep method for compatibility
        # but return a non-existent path to avoid accidental reads.
        return ""

    def _migrate_legacy_profile_once(self) -> None:
        import os, shutil
        new_path = self._profile_path()
        if os.path.exists(new_path):
            return
        # Look for legacy profile to migrate
        legacy_base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AICompanion")
        legacy = os.path.join(legacy_base, "profile.json")
        try:
            if os.path.exists(legacy):
                base_dir = os.path.dirname(new_path)
                os.makedirs(base_dir, exist_ok=True)
                shutil.copy2(legacy, new_path)
        except Exception:
            pass

    def _load_profile(self) -> None:
        import json, os
        path = self._profile_path()
        if not os.path.exists(path):
            return
        try:
            data = json.loads(open(path, "r", encoding="utf-8").read())
        except Exception:
            return
        try:
            sz = data.get("window_size")
            if isinstance(sz, list) and len(sz) == 2 and all(isinstance(i, int) for i in sz):
                self.resize(sz[0], sz[1])
        except Exception:
            pass
        self._set_model_combo_value(data.get("model", "llama3"))
        self.system_edit.setText(data.get("system_prompt", self.system_edit.text()))
        self.speak_enabled = bool(data.get("speak_enabled", self.speak_enabled))
        self.speak_toggle.setChecked(self.speak_enabled)
        self.speak_toggle.setText("Voice: On" if self.speak_enabled else "Voice: Off")
        self.anyllm_enable.setChecked(bool(data.get("anyllm_enabled", False)))
        self.anyllm_base.setText(data.get("anyllm_base", self.anyllm_base.text()))
        self.anyllm_key.setText(data.get("anyllm_key", ""))
        self.anyllm_workspace.setText(data.get("anyllm_workspace", ""))
        mode = data.get("anyllm_mode")
        if mode and mode in ["Augment (RAG)", "Responder"]:
            self.anyllm_mode.setCurrentText(mode)
        self.anyllm_thread_id = data.get("anyllm_thread_id")
        self._setup_anyllm_probe()
        assistant_n = data.get("assistant_name")
        user_n = data.get("user_name")
        if assistant_n:
            self.assistant_name_edit.setText(assistant_n)
        if user_n:
            self.user_name_edit.setText(user_n)
        # Load local model settings if present
        try:
            local_path = data.get("local_model_path", "")
            if local_path and hasattr(self, 'local_model_path_edit'):
                self.local_model_path_edit.setText(local_path)
            local_enabled = bool(data.get("local_model_enabled", False))
            if local_enabled and hasattr(self, 'local_model_chk'):
                self.local_model_chk.setChecked(True)
                if local_path:
                    try:
                        self.local_llm_client = LlamaCppClient(local_path)
                    except Exception:
                        # If loading fails, unset checkbox and inform user later via health check
                        self.local_model_chk.setChecked(False)
                        self.local_llm_client = None
        except Exception:
            pass
        try:
            self.anyllm_log_history.setChecked(bool(data.get("anyllm_log_history", False)))
        except Exception:
            pass
        try:
            tgt = data.get("anyllm_log_target", "Documents")
            if hasattr(self, 'anyllm_log_target') and tgt in ("Documents", "Chat History"):
                self.anyllm_log_target.setCurrentText(tgt)
        except Exception:
            pass
        try:
            enter_sends = bool(data.get("enter_sends", True))
            self.enter_send_chk.setChecked(enter_sends)
        except Exception:
            pass
        try:
            auto_intro = bool(data.get("auto_intro", True))
            self.auto_intro_chk.setChecked(auto_intro)
        except Exception:
            pass
        try:
            self.on_enter_sends_changed()
        except Exception:
            pass
        # Load response length settings and brevity toggle
        try:
            target = int(data.get("response_target", 3))
            allow_over = bool(data.get("response_allow_overflow", True))
            brevity_on = bool(data.get("brevity_on", True))
            if hasattr(self, 'response_target_spin'):
                self.response_target_spin.setValue(max(1, min(20, target)))
            if hasattr(self, 'response_allow_overflow'):
                self.response_allow_overflow.setChecked(allow_over)
            if hasattr(self, 'brevity_toggle'):
                self.brevity_toggle.setChecked(brevity_on)
                self.brevity_toggle.setText("Brevity: On" if brevity_on else "Brevity: Off")
        except Exception:
            pass

    def _save_profile(self) -> None:
        import json
        data = {
            "model": self.model_combo.currentText().strip(),
            "system_prompt": self.system_edit.text().strip(),
            "speak_enabled": self.speak_toggle.isChecked(),
            "anyllm_enabled": self.anyllm_enable.isChecked(),
            "anyllm_base": self.anyllm_base.text().strip(),
            "anyllm_key": self.anyllm_key.text().strip(),
            "anyllm_workspace": self.anyllm_workspace.text().strip(),
            "anyllm_mode": self.anyllm_mode.currentText(),
            "anyllm_thread_id": self.anyllm_thread_id,
            "assistant_name": self.assistant_name_edit.text().strip(),
            "user_name": self.user_name_edit.text().strip(),
            "enter_sends": bool(self.enter_send_chk.isChecked()),
            "auto_intro": bool(self.auto_intro_chk.isChecked()),
            "window_size": [self.width(), self.height()],
            "response_target": int(self.response_target_spin.value()) if hasattr(self, 'response_target_spin') else 3,
            "response_allow_overflow": bool(self.response_allow_overflow.isChecked()) if hasattr(self, 'response_allow_overflow') else True,
            "brevity_on": bool(self.brevity_toggle.isChecked()) if hasattr(self, 'brevity_toggle') else True,
            "anyllm_log_history": bool(self.anyllm_log_history.isChecked()) if hasattr(self, 'anyllm_log_history') else False,
            "anyllm_log_target": self.anyllm_log_target.currentText() if hasattr(self, 'anyllm_log_target') else "Documents",
            "local_model_enabled": bool(self.local_model_chk.isChecked()) if hasattr(self, 'local_model_chk') else False,
            "local_model_path": self.local_model_path_edit.text().strip() if hasattr(self, 'local_model_path_edit') else "",
            "local_n_ctx": self.local_n_ctx,
            "local_n_threads": self.local_n_threads,
            "local_num_predict": self.local_num_predict,
        }
        try:
            with open(self._profile_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def closeEvent(self, event):  # type: ignore[override]
        try:
            self._save_profile()
        except Exception:
            pass
        return super().closeEvent(event)

    def resizeEvent(self, event):  # type: ignore[override]
        try:
            self._set_avatar_state("idle")
        except Exception:
            pass
        return super().resizeEvent(event)

    def _set_avatar_state(self, state: str) -> None:
        if state == "talk" and self.talk_movie:
            self.avatar_label.setMovie(self.talk_movie)
            self.talk_movie.start()
        elif state == "idle" and self.idle_movie:
            self.avatar_label.setMovie(self.idle_movie)
            self.idle_movie.start()
        else:
            try:
                import os
                logo = os.path.join(os.path.dirname(__file__), "assets", "aura_nexus.png")
                if os.path.exists(logo):
                    pm = QPixmap(logo)
                    if not pm.isNull():
                        self.avatar_label.setPixmap(pm.scaled(self.avatar_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        return
            except Exception:
                pass
            self.avatar_label.setText("(No avatar assets found)")

    def _poll_talking(self) -> None:
        if self.tts.speaking():
            self._set_avatar_state("talk")
        else:
            self._set_avatar_state("idle")

    def on_toggle_voice(self) -> None:
        self.speak_enabled = self.speak_toggle.isChecked()
        self.speak_toggle.setText("Voice: On" if self.speak_enabled else "Voice: Off")
        self._save_profile()

    def on_apply_settings(self) -> None:
        sel = self.model_combo.currentText().strip() or "llama3"
        # Use the validated application path
        self._apply_model_selection(sel)
        self.system_prompt = self.system_edit.text().strip()
        self.status_left.setText(f"Model set to {self.ollama.model}")
        self._setup_anyllm_probe()
        self._save_profile()
        QTimer.singleShot(0, self._update_llm_health_async)

    def on_enter_sends_changed(self, _state=None) -> None:
        try:
            self.input_edit.set_enter_sends(self.enter_send_chk.isChecked())
            self._save_profile()
        except Exception:
            pass

    def _names_tuple(self) -> tuple[str, str]:
        try:
            a = (self.assistant_name_edit.text().strip() or "Aura")
            u = (self.user_name_edit.text().strip() or "User")
            return a, u
        except Exception:
            return "Aura", "User"

    def _effective_system_prompt(self) -> str:
        base = self.system_edit.text().strip() or self.system_prompt
        a, u = self._names_tuple()
        extra = (
            "\n\nIdentity and addressing rules:\n"
            f"- Your name is {a}. Refer to yourself as {a}.\n"
            f"- The user's name is {u}. Address the user as {u}.\n"
            "- Be concise and helpful.\n"
            "- Use the user's name naturally when appropriate."
        )
        target = 3
        try:
            target = int(self.response_target_spin.value())
        except Exception:
            target = 3
        brevity_on = True
        try:
            brevity_on = self.brevity_toggle.isChecked()
        except Exception:
            brevity_on = True
        if brevity_on:
            allow_over = True
            try:
                allow_over = self.response_allow_overflow.isChecked()
            except Exception:
                allow_over = True
            extra += f"\n- Aim for about {target} sentences (or {target+2} short bullets)."
            if allow_over:
                extra += "\n- If necessary, exceed the target slightly to be accurate."
            else:
                extra += "\n- Do not exceed the target length; summarize aggressively."
        # Emphasize strict adherence to the System Prompt content
        extra += "\n- Strictly follow the System Prompt content above (persona, tone, rules)."
        return base + extra

    def _display_name(self, role: str) -> str:
        if role == "assistant":
            return self.assistant_name_edit.text().strip() or "Aura"
        if role == "user":
            return self.user_name_edit.text().strip() or "You"
        return role.capitalize()

    def append_chat(self, role: str, text: str) -> None:
        self.chat_view.append(f"<b>{self._display_name(role)}:</b> {text}")

    def on_send(self) -> None:
        try:
            text = self.input_edit.toPlainText().strip()
        except Exception:
            text = ""
        if not text:
            return
        try:
            self.input_edit.clear()
        except Exception:
            pass
        self.append_chat("user", text)
        self.messages.append(Message("user", text))
        threading.Thread(target=self._llm_task, args=(text,), daemon=True).start()

    def on_new_chat(self) -> None:
        self.messages = []
        try:
            self.chat_view.clear()
        except Exception:
            pass
        self.anyllm_thread_id = None
        self._save_profile()
        self.status_left.setText("New chat started")
        self._auto_intro_done = False
        QTimer.singleShot(10, self._auto_intro_if_needed)

    def _llm_task(self, user_text: str) -> None:
        self.status_left.setText("Thinking...")
        start_time = time.time()
        try:
            use_anyllm = self.anyllm_enable.isChecked() and self.anyllm_key.text().strip() and self.anyllm_base.text().strip()
        except Exception:
            use_anyllm = False
        reply = ""
        if use_anyllm:
            try:
                answer, sources, thread_id = self._anyllm_ask(user_text)
                self.anyllm_thread_id = thread_id
                self._save_profile()
                if self.anyllm_mode.currentText().startswith("Responder"):
                    reply = self._enforce_identity(answer)
                else:
                    context_block = answer.strip()
                    if sources:
                        context_block += "\n\nSources:\n" + "\n".join(f"- {s}" for s in sources)
                    # Truncate excessively long context to avoid overloading Ollama
                    try:
                        MAX_CONTEXT_CHARS = 4000
                        if len(context_block) > MAX_CONTEXT_CHARS:
                            context_block = context_block[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated due to length]\n"
                            try:
                                self._append_models_log("AnythingLLM context truncated to avoid large payloads")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    augmented = f"Relevant context from knowledge base:\n{context_block}\n\nUser message:\n{user_text}\n\nRespond naturally and integrate context above where useful."
                    temp_messages = self.messages[:-1] + [Message("user", augmented)]
                    reply = self._llm_chat(temp_messages, self._effective_system_prompt(), self._ollama_options_for_length())
            except Exception as e:
                # Graceful fallback to local LLM if external RAG fails
                reply = self._llm_chat(self.messages, self._effective_system_prompt(), self._ollama_options_for_length())
        else:
            reply = self._llm_chat(self.messages, self._effective_system_prompt(), self._ollama_options_for_length())
        self.messages.append(Message("assistant", reply))
        def finish():
            elapsed = (time.time() - start_time) * 1000.0
            self.latency_label.setText(f"Latency: {elapsed:0.0f} ms")
            self.append_chat("assistant", reply)
            self.status_left.setText("Ready")
            if self.speak_enabled and reply and not reply.startswith("[Error"):
                self.tts.speak_async(reply)
            try:
                if self.anyllm_enable.isChecked() and self.anyllm_log_history.isChecked():
                    self._anyllm_log_turn(user_text, reply)
            except Exception:
                pass
        self._ui_call(finish)

    def _on_browse_local_model(self) -> None:
        try:
            fn, _ = QFileDialog.getOpenFileName(self, "Select Model", "", "Models (*.gguf);;All Files (*.*)")
            if fn:
                self.local_model_path_edit.setText(fn)
        except Exception:
            pass

    def _on_scan_local_models(self) -> None:
        """Scan a directory for GGUF models and let the user pick one."""
        try:
            import os
            # Choose a directory to scan
            d = QFileDialog.getExistingDirectory(self, "Select model folder", "")
            if not d:
                return
            found = []
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith('.gguf'):
                        found.append(os.path.join(root, f))
            if not found:
                QMessageBox.information(self, "No models found", "No GGUF models found in the selected directory.")
                return
            if len(found) == 1:
                self.local_model_path_edit.setText(found[0])
                return
            # Present a short list to choose from
            items = [os.path.relpath(p, d) for p in found]
            choice, ok = QInputDialog.getItem(self, "Select Model", "Choose a model file:", items, 0, False)
            if ok and choice:
                chosen = os.path.join(d, choice)
                self.local_model_path_edit.setText(chosen)
        except Exception:
            try:
                QMessageBox.warning(self, "Scan failed", "Failed to scan for local models")
            except Exception:
                pass

    def _on_load_local_model(self) -> None: 
        try:
            path = self.local_model_path_edit.text().strip()
            if not path:
                QMessageBox.information(self, "No model selected", "Please choose a GGUF model to load.")
                return
            # Use a progress dialog and load in a background thread
            dlg = QProgressDialog("Loading model...", "Cancel", 0, 0, self)
            dlg.setWindowTitle("Loading")
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumDuration(200)
            dlg.show()
            def do_load():
                try:
                    n_ctx = int(self._n_ctx_spin.value()) if hasattr(self, '_n_ctx_spin') else self.local_n_ctx
                    n_threads = int(self._n_threads_spin.value()) if hasattr(self, '_n_threads_spin') else self.local_n_threads
                    client = LlamaCppClient(path, n_ctx=n_ctx, n_threads=n_threads)
                    # If successful, swap in main thread
                    def done():
                        try:
                            if getattr(self, 'local_llm_client', None):
                                try:
                                    self.local_llm_client.close()
                                except Exception:
                                    pass
                            self.local_llm_client = client
                            self.local_model_chk.setChecked(True)
                            self.local_n_ctx = n_ctx
                            self.local_n_threads = n_threads
                            self.local_num_predict = int(self._num_predict_spin.value()) if hasattr(self, '_num_predict_spin') else self.local_num_predict
                            QMessageBox.information(self, "Model loaded", f"Loaded model: {path}")
                            self._save_profile()
                        except Exception as e:
                            QMessageBox.critical(self, "Model load failed", f"Failed to set model: {e}")
                        finally:
                            try:
                                dlg.cancel()
                            except Exception:
                                pass
                    self._ui_call(done)
                except Exception as e:
                    def err():
                        QMessageBox.critical(self, "Model load failed", f"Failed to load model: {e}")
                        try:
                            dlg.cancel()
                        except Exception:
                            pass
                    self._ui_call(err)
            threading.Thread(target=do_load, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading model: {e}")

    def _on_import_to_ollama(self) -> None:
        try:
            path = self.local_model_path_edit.text().strip()
            if not path:
                QMessageBox.information(self, "No model selected", "Please choose a GGUF model to import to Ollama.")
                return
            # Default name based on filename
            import os
            default_name = os.path.splitext(os.path.basename(path))[0]
            name, ok = QInputDialog.getText(self, "Import to Ollama", "Model name:", text=default_name)
            if not ok or not name.strip():
                return
            dlg = QProgressDialog("Importing model to Ollama...", "Cancel", 0, 0, self)
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setMinimumDuration(200)
            dlg.show()
            import subprocess
            def run_import():
                try:
                    script = os.path.join(os.path.dirname(__file__), "tools", "import_to_ollama.ps1")
                    args = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script, "-ModelPath", path, "-Name", name, "-Force"]
                    proc = subprocess.run(args, check=False, capture_output=True, text=True)
                    out = proc.stdout + "\n" + proc.stderr
                    def done():
                        try:
                            QMessageBox.information(self, "Import complete", out)
                            # Refresh list
                            QTimer.singleShot(0, self._refresh_models_dropdown_async)
                        except Exception:
                            pass
                        finally:
                            try:
                                dlg.cancel()
                            except Exception:
                                pass
                    self._ui_call(done)
                except Exception as e:
                    def err():
                        QMessageBox.critical(self, "Import error", str(e))
                        try:
                            dlg.cancel()
                        except Exception:
                            pass
                    self._ui_call(err)
            threading.Thread(target=run_import, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error starting import: {e}")

    def _on_toggle_local_model(self) -> None:
        try:
            enabled = bool(self.local_model_chk.isChecked())
            self.local_model_enabled = enabled
            # If enabling but not loaded, attempt to load from path
            if enabled and not self.local_llm_client:
                path = self.local_model_path_edit.text().strip()
                if path:
                    # Defer to the background load flow
                    try:
                        self._on_load_local_model()
                    except Exception as e:
                        QMessageBox.critical(self, "Model load failed", f"Failed to start model load: {e}")
                        self.local_model_chk.setChecked(False)
                        self.local_model_enabled = False
                        return
            elif not enabled and self.local_llm_client:
                try:
                    # unload local model to free resources
                    self.local_llm_client.close()
                except Exception:
                    pass
                self.local_llm_client = None
            self._save_profile()
        except Exception:
            pass

    def _llm_chat(self, messages: List[Message], system_prompt: Optional[str] = None, options: Optional[Dict] = None, _retry: bool = False) -> str:
        try:
            # Prefer local model if enabled
            if getattr(self, 'local_model_chk', None) and self.local_model_chk.isChecked() and self.local_llm_client:
                try:
                    # Ensure options contains local predict if not present
                    local_options = dict(options or {})
                    if 'max_tokens' not in local_options and 'num_predict' not in local_options:
                        local_options['num_predict'] = int(self.local_num_predict or 512)
                    return self.local_llm_client.chat(messages, system_prompt, local_options)
                except Exception as e:
                    try:
                        self._append_models_log(f"Local LLM error: {e}")
                    except Exception:
                        pass
                    # Try falling back to Ollama for redundancy
                    try:
                        model_name = self.model_combo.currentText().strip() if hasattr(self, 'model_combo') else None
                        return self.ollama.chat(messages, system_prompt, options, model=model_name)
                    except Exception:
                        return f"[Local model error: {e}]"
            # Otherwise call Ollama (ensure we pass the currently selected model)
            model_name = self.model_combo.currentText().strip() if hasattr(self, 'model_combo') else None
            resp = self.ollama.chat(messages, system_prompt, options, model=model_name)
            # If the remote call indicates a connection problem, update health UI
            try:
                if isinstance(resp, str) and 'Error contacting Ollama' in resp:
                    try:
                        def ui_update():
                            try:
                                self.status_left.setText('Ollama: Connection failed')
                                self._append_models_log(f"Ollama network error: {resp}")
                                QTimer.singleShot(0, self._update_llm_health_async)
                            except Exception:
                                pass
                        self._ui_call(ui_update)
                    except Exception:
                        pass
                    # Try a single automatic retry to refresh model list and re-invoke
                    if not _retry:
                        try:
                            # schedule model list refresh on the UI thread
                            self._ui_call(lambda: QTimer.singleShot(200, lambda: self._refresh_models_dropdown_async()))
                            # Slight delay then retry once
                            return self._llm_chat(messages, system_prompt, options, _retry=True)
                        except Exception:
                            pass
            except Exception:
                pass
            return resp
        except Exception as e:
            return f"[LLM chat error: {e}]"

    def _anyllm_log_turn(self, user_text: str, assistant_text: str) -> None:
        try:
            base = self.anyllm_base.text().strip().rstrip("/")
            key = self.anyllm_key.text().strip()
            ws = self.anyllm_workspace.text().strip() or "general"
            if not base or not key or not ws:
                return
            import requests, time as _t
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            target = self.anyllm_log_target.currentText() if hasattr(self, 'anyllm_log_target') else 'Documents'
            if target == 'Chat History':
                payload = {
                    "role": "assistant",
                    "threadId": self.anyllm_thread_id or None,
                    "message": assistant_text,
                    "meta": {
                        "user": user_text,
                        "source": "AuraNexus",
                    }
                }
                url = f"{base}/api/workspaces/{ws}/chat"
                try:
                    r = requests.post(url, headers=headers, json=payload, timeout=8)
                    if r.status_code >= 400:
                        raise RuntimeError("chat endpoint not available")
                except Exception:
                    # Fallback to documents
                    payload = {
                        "title": f"Aura Nexus Chat {_t.strftime('%Y-%m-%d %H:%M:%S')}",
                        "content": f"User:\n{user_text}\n\nAssistant:\n{assistant_text}",
                        "source": "AuraNexus",
                        "tags": ["chat", "aura"],
                    }
                    url = f"{base}/api/workspaces/{ws}/documents"
                    try:
                        requests.post(url, headers=headers, json=payload, timeout=8)
                    except Exception:
                        pass
            else:
                payload = {
                    "title": f"Aura Nexus Chat {_t.strftime('%Y-%m-%d %H:%M:%S')}",
                    "content": f"User:\n{user_text}\n\nAssistant:\n{assistant_text}",
                    "source": "AuraNexus",
                    "tags": ["chat", "aura"],
                }
                url = f"{base}/api/workspaces/{ws}/documents"
                try:
                    requests.post(url, headers=headers, json=payload, timeout=8)
                except Exception:
                    pass
        except Exception:
            pass

    def on_save_and_close(self) -> None:
        # Save chat transcript to selected AnythingLLM target (if enabled), then exit
        try:
            if self.anyllm_enable.isChecked() and self.anyllm_log_history.isChecked() and self.messages:
                # Build a compact last-turn summary for quick logging
                user_text = ""
                assistant_text = ""
                for m in reversed(self.messages):
                    if not user_text and m.role == 'user':
                        user_text = m.content
                    if not assistant_text and m.role == 'assistant':
                        assistant_text = m.content
                    if user_text and assistant_text:
                        break
                self._anyllm_log_turn(user_text, assistant_text)
            self._save_profile()
        except Exception:
            pass
        try:
            self.close()
        except Exception:
            QApplication.instance().quit()

    def _enforce_identity(self, raw: str) -> str:
        try:
            a, u = self._names_tuple()
            sys_p = self.system_edit.text().strip() or self.system_prompt or ""
            instruct = (
                "Rewrite the response below so it strictly follows these rules: "
                f"Your name is {a}. The user's name is {u}. "
                "Adhere to the System Prompt content exactly (persona, tone, constraints). "
                "Preserve meaning, improve clarity if needed, and output only the final message.\n\n"
                f"System Prompt:\n{sys_p}\n\nResponse to transform:\n"
            )
            msgs = [Message("user", instruct + raw)]
            out = self._llm_chat(msgs, self._effective_system_prompt(), None)
            return out or raw
        except Exception:
            return raw

    def _ollama_options_for_length(self) -> dict:
        # Map target sentences to a rough token cap; adjust when brevity is off
        try:
            target = int(self.response_target_spin.value())
        except Exception:
            target = 3
        try:
            brevity_on = self.brevity_toggle.isChecked()
        except Exception:
            brevity_on = True
        # Approx tokens per sentence ~30-40; use 35 avg
        base_tokens = max(80, min(800, int(target * 35)))
        cap = base_tokens if brevity_on else int(base_tokens * 1.8)
        # Boundaries for safety
        cap = max(80, min(1024, cap))
        return {"num_predict": cap}

    def on_toggle_brevity(self) -> None:
        try:
            self.brevity_toggle.setText("Brevity: On" if self.brevity_toggle.isChecked() else "Brevity: Off")
        except Exception:
            pass

    def _auto_intro_if_needed(self) -> None:
        if getattr(self, "_auto_intro_done", False):
            return
        try:
            if not self.auto_intro_chk.isChecked():
                return
        except Exception:
            return
        if self.messages:
            return
        def work():
            a, u = self._names_tuple()
            prompt = f"Introduce yourself as {a} to {u}. Be warm and concise (1-2 sentences). Invite a first question."
            try:
                reply = self._llm_chat([Message("user", prompt)], self._effective_system_prompt(), None)
            except Exception:
                reply = f"Hi {u}, I'm {a}. How can I help today?"
            def ui():
                self.append_chat("assistant", reply)
                self.messages.append(Message("assistant", reply))
                self._auto_intro_done = True
            self._ui_call(ui)
        threading.Thread(target=work, daemon=True).start()

    def _anyllm_ask(self, message: str):
        import requests, json
        base = self.anyllm_base.text().strip().rstrip("/")
        key = self.anyllm_key.text().strip()
        workspace = self.anyllm_workspace.text().strip()
        if not key:
            raise ValueError("Missing AnythingLLM API key")
        a, u = self._names_tuple()
        context_prefix = (
            f"Assistant name: {a}. User name: {u}. Refer to yourself as {a} and address the user as {u}. "
        )
        header_variants = [
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
            {"X-API-KEY": key, "Content-Type": "application/json", "Accept": "application/json"},
        ]
        generic_endpoints = ["/api/v1/ask", "/api/ask"]
        workspace_endpoints = ["/api/v1/workspaces/{ws}/ask", "/api/workspaces/{ws}/ask"]
        payload_base = {"message": context_prefix + message}
        if self.anyllm_thread_id:
            payload_base["threadId"] = self.anyllm_thread_id
        if workspace:
            payload_base["workspaceSlug"] = workspace
        data = None
        last_error: Optional[Exception] = None
        for headers in header_variants:
            for ep in generic_endpoints:
                url = f"{base}{ep}"
                try:
                    r = requests.post(url, headers=headers, json=payload_base, timeout=30)
                    if r.status_code == 404:
                        raise RuntimeError("not found")
                    r.raise_for_status()
                    data = r.json()
                    break
                except Exception as e:
                    last_error = e
            if data:
                break
        if not data:
            if not workspace:
                raise ValueError("Workspace slug required; generic ask failed.") from last_error
            for headers in header_variants:
                for ep in workspace_endpoints:
                    url = f"{base}{ep.replace('{ws}', workspace)}"
                    try:
                        ws_payload = {"message": message}
                        if self.anyllm_thread_id:
                            ws_payload["threadId"] = self.anyllm_thread_id
                        r = requests.post(url, headers=headers, json=ws_payload, timeout=30)
                        r.raise_for_status()
                        data = r.json()
                        break
                    except Exception as e:
                        last_error = e
                if data:
                    break
        if not data:
            raise RuntimeError(f"AnythingLLM request failed: {last_error}")
        answer = data.get("answer") or data.get("response") or data.get("message") or ""
        sources = data.get("sources") or data.get("citations") or []
        thread_id = data.get("threadId") or data.get("thread_id") or self.anyllm_thread_id
        return answer, sources, thread_id

    def _set_model_combo_value(self, value: str) -> None:
        try:
            items = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            if value and value not in items:
                self.model_combo.addItem(value)
            if value:
                self.model_combo.setCurrentText(value)
        except Exception:
            pass

    def _apply_model_selection(self, sel: str) -> None:
        try:
            # ensure sel is in the model list before applying
            items = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            if sel and sel not in items:
                # warn the user and do not set the model
                self.status_left.setText(f"Model not available: {sel}")
                try:
                    self.llm_health.setText('Model Not Available')
                    self.llm_health.setStyleSheet("color: #d88; font-weight: bold")
                except Exception:
                    pass
                self._append_models_log(f"Attempted to select model not in Ollama: {sel}")
                QTimer.singleShot(0, self._update_llm_health_async)
                return
            self.ollama.model = sel or "llama3"
            self.status_left.setText(f"Model set to {self.ollama.model}")
            QTimer.singleShot(0, self._update_llm_health_async)
        except Exception as e:
            self.status_left.setText(f"Model selection error: {e}")
            self._append_models_log(f"Model selection error: {e}")

    def _on_model_combo_changed(self) -> None:
        try:
            # Defer actual model application to allow the model list to refresh
            sel = self.model_combo.currentText().strip() or "llama3"
            self.status_left.setText(f"Model selection changed: {sel}")
            QTimer.singleShot(400, lambda: self._apply_model_selection(sel))
        except Exception:
            pass

    def _refresh_models_dropdown_async(self) -> None:
        def work():
            names: list[str] = []
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                if r.status_code < 400:
                    data = r.json()
                    raw = data.get("models") or data.get("tags") or []
                    tmp: list[str] = []
                    for m in raw:
                        name = (
                            (m.get("model") if isinstance(m, dict) else None)
                            or (m.get("name") if isinstance(m, dict) else None)
                            or (str(m) if not isinstance(m, dict) else None)
                        )
                        if not name:
                            continue
                        base = str(name).split(":")[0]
                        tmp.append(base)
                    seen = set()
                    for n in tmp:
                        if n not in seen:
                            seen.add(n)
                            names.append(n)
            except Exception:
                try:
                    self._append_models_log("Failed to fetch models from Ollama (refresh)")
                except Exception:
                    pass
            if not names:
                names = ["llama3"]
            current = self.model_combo.currentText() if self.model_combo.count() else "llama3"
            def update():
                self.model_combo.clear()
                for n in names:
                    self.model_combo.addItem(n)
                if current in names:
                    self.model_combo.setCurrentText(current)
                else:
                    self.model_combo.setCurrentIndex(0)
                self.ollama.model = self.model_combo.currentText()
                self.status_left.setText(f"Models refreshed ({len(names)} found)")
                QTimer.singleShot(0, self._update_llm_health_async)
            self._ui_call(update)
        threading.Thread(target=work, daemon=True).start()

    def _ui_call(self, fn):
        try:
            self._invoker.call.emit(fn)
        except Exception:
            pass

    def on_test_chat(self) -> None:
        def work():
            import json
            model = self.model_combo.currentText().strip() or "llama3"
            result = ""
            start_time = time.time()
            try:
                # If a local model is enabled and loaded, use it for a quick test
                if getattr(self, 'local_model_chk', None) and self.local_model_chk.isChecked() and self.local_llm_client:
                    temp_messages = [Message("user", "Say hi")]
                    try:
                        result = self._llm_chat(temp_messages, self._effective_system_prompt(), {})
                    except Exception as e:
                        result = f"[Test chat error (local): {e}]"
                else:
                    try:
                        temp_messages = [Message("user", "Say hi")]
                        result = self._llm_chat(temp_messages, self._effective_system_prompt(), {})
                    except Exception as e:
                        result = f"[Test chat error (ollama): {e}]"
            except Exception as e:
                result = f"[Test chat error: {e}]"
            elapsed = (time.time() - start_time) * 1000.0
            def ui():
                self.chat_view.append(f"<i>LLM Test ({model}):</i> {result}")
                self.latency_label.setText(f"Latency: {elapsed:0.0f} ms")
                self._update_llm_health_async()
            self._ui_call(ui)
        threading.Thread(target=work, daemon=True).start()

    def on_run_diagnostics(self) -> None:
        def work():
            import requests
            summary = []
            ollama_ok = False
            models = []
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=3)
                if r.status_code < 400:
                    ollama_ok = True
                    raw = r.json().get("models") or r.json().get("tags") or []
                    for m in raw:
                        name = (
                            (m.get("model") if isinstance(m, dict) else None)
                            or (m.get("name") if isinstance(m, dict) else None)
                            or (str(m) if not isinstance(m, dict) else None)
                        )
                        if name:
                            models.append(str(name).split(":")[0])
            except Exception:
                pass
            summary.append(f"Ollama: {'OK' if ollama_ok else 'DOWN'}")
            summary.append(f"Models: {', '.join(sorted(set(models))) if models else '-'}")
            sel = self.model_combo.currentText().strip() or '-'
            summary.append(f"Selected: {sel}")
            summary.append(f"HealthLbl: {self.llm_health.text()}")
            any_enabled = False
            try:
                any_enabled = self.anyllm_enable.isChecked()
            except Exception:
                pass
            summary.append(f"AnythingLLM: {'Enabled' if any_enabled else 'Disabled'}")
            gpu = self._detect_nvidia()
            summary.append(f"GPU: {'Detected' if gpu else 'None'}")
            summary.append(self.latency_label.text())
            summary.append(f"ThreadId: {self.anyllm_thread_id or '-'}")
            summary.append(f"AssistantName: {self.assistant_name_edit.text().strip() or '-'}")
            summary.append(f"UserName: {self.user_name_edit.text().strip() or '-'}")
            text = " | ".join(summary)
            def ui():
                self.chat_view.append(f"<i>Diagnostics:</i> {text}")
            self._ui_call(ui)
        threading.Thread(target=work, daemon=True).start()

    def _check_cmd(self, args: list[str]) -> bool:
        import subprocess, platform
        try:
            si = None
            creationflags = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                # Prefer Python's constant when available, fallback to literal
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.run(args, capture_output=True, text=True, check=False, startupinfo=si, creationflags=creationflags)
            return True
        except Exception:
            return False

    def _check_docker(self) -> bool:
        if self._check_cmd(["docker", "version"]):
            return True
        import os, subprocess, platform
        candidate = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker", "Docker", "resources", "bin", "docker.exe")
        try:
            si = None
            creationflags = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.run([candidate, "version"], capture_output=True, text=True, check=False, startupinfo=si, creationflags=creationflags)
            return True
        except Exception:
            return False

    def _check_ollama(self) -> bool:
        if self._check_cmd(["ollama", "--version"]):
            return True
        import requests
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            return r.status_code < 400
        except Exception:
            return False

    def on_check_dependencies(self):
        docker_ok = self._check_docker()
        ollama_ok = self._check_ollama()
        gpu = self._detect_nvidia()
        msg = []
        msg.append(f"Docker: {'OK' if docker_ok else 'Missing'}")
        msg.append(f"Ollama: {'OK' if ollama_ok else 'Missing'}")
        msg.append(f"GPU (NVIDIA): {'Detected' if gpu else 'Not detected'}")
        self.status_left.setText(" | ".join(msg))
        try:
            if hasattr(self, 'docker_status'):
                self.docker_status.setText('Online' if docker_ok else 'Offline')
                self.docker_status.setStyleSheet(f"color: {'#0a0' if docker_ok else '#a00'}; font-weight: bold")
            if hasattr(self, 'gpu_status'):
                self.gpu_status.setText('Detected' if gpu else 'Not detected')
                self.gpu_status.setStyleSheet(f"color: {'#0a0' if gpu else '#a00'}; font-weight: bold")
        except Exception:
            pass
        try:
            self.llm_health.setToolTip("GPU: " + ("Detected" if gpu else "Not detected"))
        except Exception:
            pass
        QTimer.singleShot(0, self._update_llm_health_async)

    def on_check_dependencies_async(self):
        def work():
            docker_ok = self._check_docker()
            ollama_ok = self._check_ollama()
            gpu = self._detect_nvidia()
            msg = []
            msg.append(f"Docker: {'OK' if docker_ok else 'Missing'}")
            msg.append(f"Ollama: {'OK' if ollama_ok else 'Missing'}")
            msg.append(f"GPU (NVIDIA): {'Detected' if gpu else 'Not detected'}")
            def update():
                self.status_left.setText(" | ".join(msg))
                try:
                    self.llm_health.setToolTip("GPU: " + ("Detected" if gpu else "Not detected"))
                except Exception:
                    pass
                try:
                    if hasattr(self, 'docker_status'):
                        self.docker_status.setText('Online' if docker_ok else 'Offline')
                        self.docker_status.setStyleSheet(f"color: {'#0a0' if docker_ok else '#a00'}; font-weight: bold")
                    if hasattr(self, 'gpu_status'):
                        self.gpu_status.setText('Detected' if gpu else 'Not detected')
                        self.gpu_status.setStyleSheet(f"color: {'#0a0' if gpu else '#a00'}; font-weight: bold")
                except Exception:
                    pass
                QTimer.singleShot(0, self._update_llm_health_async)
            self._ui_call(update)
        threading.Thread(target=work, daemon=True).start()

    def _update_gpu_status(self) -> None:
        gpu = self._detect_nvidia()
        try:
            if hasattr(self, 'gpu_status'):
                self.gpu_status.setText('Detected' if gpu else 'Not detected')
                self.gpu_status.setStyleSheet(f"color: {'#0a0' if gpu else '#a00'}; font-weight: bold")
        except Exception:
            pass
        self.services_console.append(f"GPU check: {'Detected' if gpu else 'Not detected'}")

    def on_force_connect(self) -> None:
        ans = QMessageBox.question(
            self,
            "Connect Services",
            "Attempt to start Docker Desktop and detect Ollama?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if ans != QMessageBox.Yes:
            return
        threading.Thread(target=self._force_connect_work, daemon=True).start()

    def _force_connect_work(self) -> None:
        if not self._check_docker():
            try:
                import os, subprocess, platform
                exe = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker", "Docker", "Docker Desktop.exe")
                si = None
                creationflags = 0
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    # Combine no-window with detached process for GUI apps
                    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    creationflags = no_window | detached
                subprocess.Popen([exe], close_fds=True, startupinfo=si, creationflags=creationflags)
                time.sleep(8)
            except Exception:
                pass
        if not self._check_ollama():
            try:
                import os, subprocess, platform
                ollama_exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
                si = None
                creationflags = 0
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    creationflags = no_window | detached
                subprocess.Popen([ollama_exe, "serve"], close_fds=True, startupinfo=si, creationflags=creationflags)
                time.sleep(3)
            except Exception:
                pass
        self._ui_call(self.on_check_dependencies)
        self._ui_call(self._refresh_models_dropdown_async)

    def _detect_nvidia(self) -> bool:
        import subprocess, platform
        try:
            si = None
            creationflags = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            r = subprocess.run(["nvidia-smi"], capture_output=True, text=True, startupinfo=si, creationflags=creationflags)
            return r.returncode == 0
        except Exception:
            return False

    def _detect_providers_async(self) -> None:
        def work():
            import requests
            oll = False
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=2)
                oll = r.status_code < 400
            except Exception:
                oll = False
            def update():
                parts = []
                parts.append(f"Ollama: {'Detected' if oll else 'Not found'}")
                self.models_status.setText(" | ".join(parts))
                self.oll_detect_label.setText("Detected" if oll else "Not found")
                if oll:
                    self._refresh_models_dropdown_async()
                self._update_llm_health_async()
            self._ui_call(update)
        threading.Thread(target=work, daemon=True).start()

    def _append_models_log(self, text: str) -> None:
        self.models_console.append(text)

    def _start_ollama_async(self) -> None:
        def work():
            import os, subprocess, platform, time as _t
            try:
                si = None
                creationflags = 0
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    creationflags = no_window | detached
                exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
                subprocess.Popen([exe, "serve"], close_fds=True, startupinfo=si, creationflags=creationflags)
                _t.sleep(2)
            except Exception:
                pass
            self._ui_call(self._update_llm_health_async)
        threading.Thread(target=work, daemon=True).start()

    def on_ollama_pull(self) -> None:
        def work():
            import subprocess, os, platform
            model = self.oll_model_input.text().strip() or "llama3"
            try:
                si = None
                creationflags = 0
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.run(["ollama", "pull", model], check=False, timeout=600, startupinfo=si, creationflags=creationflags)
            except Exception:
                pass
            try:
                exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
                si = None
                creationflags = 0
                if platform.system() == "Windows":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.run([exe, "pull", model], check=False, timeout=600, startupinfo=si, creationflags=creationflags)
            except Exception:
                pass
            self._ui_call(lambda: self._append_models_log(f"Pulled model: {model}"))
            self._ui_call(self._refresh_models_dropdown_async)
            self._ui_call(self._update_llm_health_async)
        threading.Thread(target=work, daemon=True).start()

    def on_ollama_list(self) -> None:
        def work():
            import subprocess
            out = ""
            try:
                si = None
                creationflags = 0
                if sys.platform.startswith("win"):
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                p = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True, timeout=15, startupinfo=si, creationflags=creationflags)
                out = (p.stdout or p.stderr or "").strip()
            except Exception:
                pass
            if not out:
                out = "(no output)"
            self._ui_call(lambda: self._append_models_log(out))
        threading.Thread(target=work, daemon=True).start()
    def _setup_anyllm_probe(self) -> None:
        enabled = self.anyllm_enable.isChecked()
        if not hasattr(self, "anyllm_probe_timer"):
            self.anyllm_probe_timer = QTimer(self)
            self.anyllm_probe_timer.setInterval(5000)
            self.anyllm_probe_timer.timeout.connect(self._probe_anyllm)
        if enabled:
            if not self.anyllm_probe_timer.isActive():
                self.anyllm_probe_timer.start()

    def on_avatar_connect(self) -> None:
        try:
            from avatar.vts_controller import VTSController
        except Exception:
            QMessageBox.warning(self, "Avatar", "Install dependencies via run_aura_nexus.ps1 (websocket-client)")
            return
        if self.avatar_provider.currentText() in ("None", "OBS Face Tracker"):
            QMessageBox.information(self, "Avatar", "Selected provider does not require a WebSocket connection from Aura Nexus.")
            return
        host = self.avatar_host.text().strip()
        try:
            port = int(self.avatar_port.text().strip())
        except Exception:
            port = 8001
        self._vts = VTSController(host=host, port=port)
        if not self._vts.available():
            QMessageBox.warning(self, "Avatar", "websocket-client not available")
            return
        if self._vts.connect():
            QMessageBox.information(self, "Avatar", f"Connected to VTS at ws://{host}:{port}")
            self._vts.disconnect()
        else:
            QMessageBox.warning(self, "Avatar", f"Failed to connect to VTS at ws://{host}:{port}")

    def on_avatar_test(self) -> None:
        try:
            from avatar.vts_controller import VTSController
        except Exception:
            QMessageBox.warning(self, "Avatar", "Install dependencies via run_aura_nexus.ps1 (websocket-client)")
            return
        if self.avatar_provider.currentText() in ("None", "OBS Face Tracker"):
            QMessageBox.information(self, "Avatar", "Selected provider test not applicable here.")
            return
        host = self.avatar_host.text().strip() if hasattr(self, 'avatar_host') else 'localhost'
        port_text = self.avatar_port.text().strip() if hasattr(self, 'avatar_port') else '8001'
        try:
            port = int(port_text)
        except Exception:
            port = 8001
        ctl = VTSController(host=host, port=port)
        if not ctl.available():
            QMessageBox.warning(self, "Avatar", "websocket-client not available")
            return
        ok = ctl.connect()
        if not ok:
            QMessageBox.warning(self, "Avatar", f"VTube Studio not reachable at ws://{host}:{port}. Please open VTS and enable API.")
            return
        try:
            test_ok = ctl.test_emote()
        finally:
            ctl.disconnect()
        if test_ok:
            QMessageBox.information(self, "Avatar", "Connected to VTS and sent test emote.")
        else:
            QMessageBox.information(self, "Avatar", "Connected, but parameter update may not be visible. Check model parameters.")

    def _load_avatar_profile(self) -> None:
        try:
            import os, json
            base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "AuraNexus")
            os.makedirs(base, exist_ok=True)
            prof = os.path.join(base, "profile.json")
            if not os.path.exists(prof):
                return
            with open(prof, "r", encoding="utf-8") as f:
                data = json.load(f)
            av = data.get("avatar", {})
            provider = av.get("provider")
            atype = av.get("type")
            abody = av.get("body")
            host = av.get("host")
            port = av.get("port")
            if provider is not None and hasattr(self, 'avatar_provider'):
                idx = self.avatar_provider.findText(provider)
                if idx >= 0:
                    self.avatar_provider.setCurrentIndex(idx)
            if atype is not None and hasattr(self, 'avatar_type'):
                idx = self.avatar_type.findText(atype)
                if idx >= 0:
                    self.avatar_type.setCurrentIndex(idx)
            if abody is not None and hasattr(self, 'avatar_body'):
                idx = self.avatar_body.findText(abody)
                if idx >= 0:
                    self.avatar_body.setCurrentIndex(idx)
            if host and hasattr(self, 'avatar_host'):
                self.avatar_host.setText(str(host))
            if port and hasattr(self, 'avatar_port'):
                self.avatar_port.setText(str(port))
        except Exception:
            pass

    def _save_avatar_profile(self) -> None:
        try:
            import os, json
            base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "AuraNexus")
            os.makedirs(base, exist_ok=True)
            prof = os.path.join(base, "profile.json")
            data = {}
            if os.path.exists(prof):
                try:
                    with open(prof, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["avatar"] = {
                "provider": self.avatar_provider.currentText() if hasattr(self, 'avatar_provider') else "None",
                "type": self.avatar_type.currentText() if hasattr(self, 'avatar_type') else "2D",
                "body": self.avatar_body.currentText() if hasattr(self, 'avatar_body') else "Head",
                "host": self.avatar_host.text().strip() if hasattr(self, 'avatar_host') else "localhost",
                "port": self.avatar_port.text().strip() if hasattr(self, 'avatar_port') else "8001",
            }
            with open(prof, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.status_left.setText("Avatar settings saved")
        except Exception:
            pass

    def _probe_anyllm(self) -> None:
        """Check AnythingLLM health status."""
        if not self.anyllm_enable.isChecked():
            return
        base = self.anyllm_base.text().strip().rstrip("/")
        if not base:
            return
        url_candidates = [f"{base}/api/docs", f"{base}/api/v1/health", f"{base}/api/health"]
        status = "Offline"
        color = "#a00"
        
        # Use httpx if available (from AsyncOllamaClient dependencies), otherwise fallback
        try:
            import httpx
            for u in url_candidates:
                try:
                    resp = httpx.get(u, timeout=2.0)
                    if resp.status_code < 400:
                        status = "Online"
                        color = "#0a0"
                        break
                except Exception:
                    continue
        except ImportError:
            # Fallback to requests
            import requests
            for u in url_candidates:
                try:
                    r = requests.get(u, timeout=2)
                    if r.status_code < 400:
                        status = "Online"
                        color = "#0a0"
                        break
                except Exception:
                    continue
        
        if hasattr(self, "anyllm_status"):
            try:
                self.anyllm_status.setText(status)
                self.anyllm_status.setStyleSheet(f"color: {color}; font-weight: bold")
            except Exception:
                pass

    def _update_llm_health_async(self) -> None:
        """Check Ollama health using AsyncOllamaClient."""
        import time as _t
        now = _t.time()
        if getattr(self, "_last_llm_health_ts", 0) and (now - self._last_llm_health_ts) < 0.4:
            return
        self._last_llm_health_ts = now
        
        def work():
            status = "Offline"
            color = "#a00"
            detail = ""
            version = ""
            
            # Use upgraded AsyncOllamaClient for health check
            if AsyncOllamaClient:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        async def check():
                            async with AsyncOllamaClient() as client:
                                # Fast health check
                                healthy = await client.health_check()
                                if not healthy:
                                    return "Offline", "#a00", "", ""
                                
                                # Get version
                                ver = await client.get_version()
                                
                                # List models
                                models = await client.list_models()
                                names = [m.split(':')[0] for m in models]
                                
                                cur = self.model_combo.currentText().strip() or "llama3"
                                if names:
                                    if cur in names or cur in models:
                                        return "Ready", "#0a0", f"Ollama {ver} | Current: {cur} | Available: {', '.join(sorted(set(names)))}", ver
                                    else:
                                        return "No model", "#d88", f"Ollama {ver} | Current: {cur} (not found) | Available: {', '.join(sorted(set(names)))}", ver
                                return "No models", "#d88", f"Ollama {ver} | No models installed", ver
                        
                        status, color, detail, version = loop.run_until_complete(check())
                    finally:
                        loop.close()
                except Exception as e:
                    status = "Offline"
                    color = "#a00"
                    detail = f"Error: {e}"
                    try:
                        self.services_console.append(f"Ollama health check failed: {e}")
                    except Exception:
                        pass
            else:
                # Fallback to basic check if imports failed
                try:
                    import requests
                    r = requests.get("http://localhost:11434/api/tags", timeout=2)
                    if r.status_code < 400:
                        status = "Ready (legacy)"
                        color = "#0a0"
                except Exception:
                    pass
            
            def ui_update():
                prior_status = getattr(self, "_last_llm_health_status", None)
                prior_detail = getattr(self, "_last_llm_health_detail", None)
                self.llm_health.setText(status)
                self.llm_health.setStyleSheet(f"color: {color}; font-weight: bold")
                if detail:
                    self.llm_health.setToolTip(detail)
                
                # If using a local GGUF model, prioritize its health status
                try:
                    if getattr(self, 'local_model_chk', None) and self.local_model_chk.isChecked():
                        if getattr(self, 'local_llm_client', None):
                            self.llm_health.setText("Local Ready")
                            self.llm_health.setStyleSheet(f"color: #0a0; font-weight: bold")
                            self.llm_health.setToolTip(f"Local model: {self.local_model_path_edit.text().strip()}")
                        else:
                            self.llm_health.setText("Local Missing")
                            self.llm_health.setStyleSheet(f"color: #d88; font-weight: bold")
                except Exception:
                    pass
                
                # Services tab Ollama mirror
                if hasattr(self, 'ollama_status'):
                    ollama_txt = f"{status}"
                    if version:
                        ollama_txt = f"{status} (v{version})"
                    self.ollama_status.setText(ollama_txt)
                    self.ollama_status.setStyleSheet(f"color: {color}; font-weight: bold")
                
                if (status != prior_status) or (detail and detail != prior_detail):
                    if detail:
                        self.chat_view.append(f"<i>LLM Health:</i> {detail}")
                        if hasattr(self, 'services_console'):
                            self.services_console.append(f"LLM: {status} | {detail}")
                
                self._last_llm_health_status = status
                self._last_llm_health_detail = detail
            
            self._ui_call(ui_update)
        
        threading.Thread(target=work, daemon=True).start()

def main() -> int:
    app = QApplication(sys.argv)
    try:
        app.setApplicationName("Aura Nexus")
        app.setApplicationDisplayName("Aura Nexus")
        app.setOrganizationName("AuraNexus")
    except Exception:
        pass
    try:
        import os
        base = os.path.join(os.path.dirname(__file__), "assets")
        icon_png = os.path.join(base, "aura_nexus.png")
        icon_ico = os.path.join(base, "aura_nexus.ico")
        if os.path.exists(icon_ico):
            app.setWindowIcon(QIcon(icon_ico))
        elif os.path.exists(icon_png):
            app.setWindowIcon(QIcon(icon_png))
    except Exception:
        pass
    win = AuraNexusWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
