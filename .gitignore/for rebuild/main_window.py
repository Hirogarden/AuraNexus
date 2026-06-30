"""
Main application window.

Layout
------
Left sidebar  — mode buttons + settings toggle
Centre panel  — chat area (Companion) or story area (You'niverse)
Right drawer  — settings panel (slides in/out)

The window is intentionally simple: PySide6 only, no Tauri/React.
"""
from __future__ import annotations

import json
import hashlib
import threading
import queue
from time import monotonic
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QByteArray, QThread, QTimer, Signal, QObject, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from auranexus.ui.settings_panel import SettingsPanel
from auranexus.ui.memory_panel import MemoryPanel
from auranexus.ui.lorebook_panel import LorebookPanel
from auranexus.ui.knowledge_panel import KnowledgePanel
from auranexus.engine.secret_store import load_secrets, scrub_and_store_secrets
from nexus_core_enhancements import CitationManager
from nexus_doc_store import DEV_MODE
from auranexus.story.scenario_dialog import ScenarioDialog, SavedScenariosDialog
from auranexus.tts.espeak_provider import EspeakProvider
from auranexus.tts.tts_router import TTSRouter
from auranexus.stt.recorder import MicRecorder
from auranexus.stt.transcriber import WhisperTranscriber
from auranexus.ui.writing_canvas import WritingCanvas
from auranexus.hardware.model_catalog import build_fit_warning


# ---------------------------------------------------------------------------
# Edit warning dialog (runtime suppression — resets on restart)
# ---------------------------------------------------------------------------

class _EditWarningDialog(QMessageBox):
    """
    Warning shown the first time the user manually edits a narrator response.

    Suppression is stored as a class-level bool so it resets when the program
    is restarted, matching the "per program launch" requirement.
    """

    _suppressed: bool = False

    @classmethod
    def maybe_show(cls, parent=None) -> bool:
        """Show the dialog unless suppressed.  Returns True to continue the edit."""
        if cls._suppressed:
            return True
        dlg = cls(parent)
        result = dlg.exec()
        return result == QMessageBox.StandardButton.Ok

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Response — Warning")
        self.setIcon(QMessageBox.Icon.Warning)
        self.setText(
            "<b>You are about to manually edit a narrator response.</b>"
        )
        self.setInformativeText(
            "Editing a response can cause the story to become inconsistent if the "
            "new text contradicts events that are already part of the narrative or "
            "stored in memory.\n\n"
            "This warning applies to any story, not just this one."
        )
        dont_show_cb = QCheckBox("Don't show this again this session")
        self.setCheckBox(dont_show_cb)
        self.addButton(QMessageBox.StandardButton.Ok)
        self.addButton(QMessageBox.StandardButton.Cancel)
        self.setDefaultButton(QMessageBox.StandardButton.Ok)

        # We check after exec — setCheckBox's widget is managed by QMessageBox
        self._cb = dont_show_cb

    def exec(self) -> int:
        result = super().exec()
        if self._cb.isChecked():
            _EditWarningDialog._suppressed = True
        return result


# ---------------------------------------------------------------------------
# Background worker — streams LLM tokens on a separate thread
# ---------------------------------------------------------------------------

class _StreamWorker(QObject):
    token_received = Signal(str)
    stream_done = Signal()
    error_occurred = Signal(str)

    def __init__(self, core, prompt: str) -> None:
        super().__init__()
        self._core = core
        self._prompt = prompt
        self._stop_requested = False

    def request_stop(self) -> None:
        """Call from the main thread to abort streaming after the next token."""
        self._stop_requested = True

    @Slot()
    def run(self) -> None:
        # P23: Protect UI against indefinite model hangs with a hard timeout.
        timeout_s = 300.0
        token_q: queue.Queue = queue.Queue()
        err_q: queue.Queue = queue.Queue()

        def _stream_target() -> None:
            try:
                for token in self._core.stream(self._prompt):
                    token_q.put(token)
            except Exception as exc:  # noqa: BLE001
                err_q.put(str(exc))
            finally:
                token_q.put(None)

        stream_thread = threading.Thread(target=_stream_target, daemon=True)
        stream_thread.start()

        try:
            deadline = monotonic() + timeout_s
            while True:
                if self._stop_requested:
                    break
                remaining = deadline - monotonic()
                if remaining <= 0:
                    self.error_occurred.emit("Streaming timed out after 5 minutes. Please try a smaller prompt or model.")
                    break
                try:
                    item = token_q.get(timeout=min(0.2, remaining))
                except queue.Empty:
                    continue
                if item is None:
                    break
                self.token_received.emit(item)

            if not err_q.empty():
                self.error_occurred.emit(err_q.get())
        finally:
            self.stream_done.emit()


# ---------------------------------------------------------------------------
# STT background worker
# ---------------------------------------------------------------------------

class _STTWorker(QObject):
    transcription_done = Signal(str)

    def __init__(self, transcriber, audio) -> None:
        super().__init__()
        self._transcriber = transcriber
        self._audio = audio

    @Slot()
    def run(self) -> None:
        from auranexus.stt.recorder import MicRecorder
        result = self._transcriber.transcribe(
            self._audio, sample_rate=MicRecorder.SAMPLE_RATE
        )
        self.transcription_done.emit(result)


class _IngestWorker(QObject):
    """Runs document ingestion off the main thread."""
    done = Signal(list)      # list of result dicts
    progress = Signal(str)   # status message for the status bar

    _MAX_FILES = 200  # hard cap — warn and skip the rest

    def __init__(self, core, paths: list) -> None:
        super().__init__()
        self._core = core
        self._paths = paths

    @staticmethod
    def _expand_paths(paths: list) -> list[str]:
        """Expand directories into files (recursive) and filter to supported extensions."""
        supported_exts = {
            ".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".rst", ".log",
        }
        expanded: list[str] = []
        seen: set[str] = set()
        for p in paths:
            try:
                path = Path(p)
            except Exception:  # noqa: BLE001
                continue

            if path.is_dir():
                for fp in path.rglob("*"):
                    if not fp.is_file():
                        continue
                    if fp.suffix.lower() not in supported_exts:
                        continue
                    s = str(fp)
                    if s not in seen:
                        seen.add(s)
                        expanded.append(s)
                continue

            if path.suffix.lower() not in supported_exts:
                continue
            s = str(path)
            if s not in seen:
                seen.add(s)
                expanded.append(s)
        return expanded

    @Slot()
    def run(self) -> None:
        expanded = self._expand_paths(self._paths)
        capped = False
        if len(expanded) > self._MAX_FILES:
            capped = True
            expanded = expanded[: self._MAX_FILES]

        results: list = []
        total = len(expanded)
        for i, path in enumerate(expanded, 1):
            self.progress.emit(f"Ingesting file {i}/{total}: {Path(path).name}")
            result = self._core.ingest_documents([path])
            results.extend(result)

        if capped:
            results.append({
                "status": "skipped",
                "filename": "…",
                "chunks_created": 0,
                "message": f"Stopped at {self._MAX_FILES} files — import the rest separately",
            })

        self.done.emit(results)


# ---------------------------------------------------------------------------
# Sidebar button
# ---------------------------------------------------------------------------

class _SideButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                border-left: 3px solid transparent;
                text-align: left;
                padding-left: 12px;
                font-size: 14px;
            }
            QPushButton:checked {
                border-left: 3px solid #7a8fe8;
                font-weight: bold;
            }
            QPushButton:hover:!checked {
                background: rgba(255,255,255,0.05);
            }
            """
        )


# ---------------------------------------------------------------------------
# Chat bubble display
# ---------------------------------------------------------------------------

class ChatView(QTextEdit):
    """Read-only rich text display for the chat history."""

    _FMT_USER   = None  # populated on first use
    _FMT_SYSTEM = None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("ChatView")
        self._current_bubble_open = False
        self._stream_fmt: QTextCharFormat | None = None
        # Track where the current assistant bubble's *content* starts so we
        # can replace it (e.g. to strip raw TOOL_CALL blocks after streaming).
        self._bubble_content_start: int | None = None
        self._bubble_fmt_saved: QTextCharFormat | None = None

    # ------------------------------------------------------------------
    # Internal helpers for character formats (avoids repeated allocations)
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(700)
        return f

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_user(self, name: str, text: str, timestamp: str = "") -> None:
        self._close_bubble()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        if timestamp:
            cursor.insertText(f"[{timestamp}] ", self._fmt("#585b70"))
        cursor.insertText(f"{name}: ", self._fmt("#a0c4ff", bold=True))
        cursor.insertText(text,          self._fmt("#a0c4ff"))
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def start_assistant(self, aura_name: str, timestamp: str = "") -> None:
        """Begin a streaming assistant bubble."""
        self._close_bubble()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        if timestamp:
            cursor.insertText(f"[{timestamp}] ", self._fmt("#585b70"))
        cursor.insertText(f"{aura_name}: ", self._fmt("#c3e6cb", bold=True))
        # Format for streamed tokens — same colour, normal weight
        self._stream_fmt = self._fmt("#c3e6cb")
        self._bubble_fmt_saved = self._stream_fmt
        self._bubble_content_start = cursor.position()  # right after the prefix
        self.setTextCursor(cursor)
        self._current_bubble_open = True

    def stream_token(self, token: str) -> None:
        """Append one streaming token.  Uses insertText so spaces are preserved."""
        if not self._current_bubble_open or self._stream_fmt is None:
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token, self._stream_fmt)   # literal — no HTML whitespace rules
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def close_assistant(self) -> None:
        # Nothing special to close when using insertText — just update state.
        self._current_bubble_open = False
        self._stream_fmt = None

    def replace_last_assistant_content(self, text: str) -> None:
        """Replace everything from the bubble content start to end-of-document."""
        if self._bubble_content_start is None:
            return
        fmt = self._bubble_fmt_saved or self._fmt("#c3e6cb")
        cursor = self.textCursor()
        cursor.setPosition(self._bubble_content_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.removeSelectedText()
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _close_bubble(self) -> None:
        if self._current_bubble_open:
            self.close_assistant()

    def remove_last_exchange(self) -> None:
        """Remove the last two blocks (user + assistant) from the view.

        Used by rewrite and rollback to visually undo the last turn.
        Works by removing paragraphs from the end until two non-empty
        block-starts have been removed, or the document is empty.
        """
        doc = self.document()
        # Collect block positions from the end
        # We'll remove from the last block backwards until we've cleared
        # two "speaker prefix" blocks (user + assistant).
        removed = 0
        cursor = QTextCursor(doc)
        while removed < 2 and not doc.isEmpty():
            cursor.movePosition(QTextCursor.MoveOperation.End)
            # Select the last block
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            block_text = cursor.selectedText().strip()
            cursor.removeSelectedText()
            # Remove the block separator too
            cursor.deletePreviousChar()
            if block_text:
                removed += 1
        self._bubble_content_start = None

    def replace_last_narrator_content(self, text: str) -> None:
        """Replace the last assistant bubble's content with *text*.

        Used by the Edit Response feature after the user edits a beat.
        Falls back to replace_last_assistant_content if the bubble start
        cursor is still available.
        """
        if self._bubble_content_start is not None:
            self.replace_last_assistant_content(text)
            return
        # bubble_content_start was cleared — find the last assistant line
        # and replace everything after its ': ' prefix.
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        block = cursor.block()
        # Walk backwards to find a non-empty block
        while block.isValid():
            txt = block.text()
            if txt.strip():
                colon_idx = txt.find(": ")
                if colon_idx != -1:
                    # Position cursor after the ': ' prefix
                    cursor.setPosition(block.position() + colon_idx + 2)
                    cursor.movePosition(
                        QTextCursor.MoveOperation.EndOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.removeSelectedText()
                    cursor.insertText(text, self._fmt("#c3e6cb"))
                    self.setTextCursor(cursor)
                    return
            block = block.previous()

    def append_system(self, text: str) -> None:
        self._close_bubble()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        cursor.insertText(text, self._fmt("#888888"))
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    _CONFIG_PATH = Path.home() / ".config" / "auranexus" / "settings.json"

    def __init__(self, core) -> None:
        """
        Parameters
        ----------
        core : auranexus.core.AuraNexusCore
            The glue object that owns the LLM provider + memory.
        """
        super().__init__()
        self._core = core
        self._streaming = False
        self._pending_user_message = ""
        self._pending_ts = ""                    # timestamp when user pressed Send
        self._accumulated_response = ""   # built token-by-token; avoids HTML parse
        self._active_view: ChatView | None = None  # current chat/story view
        self._stream_is_opening = False            # True for story opening narration
        self._citation_manager = CitationManager()
        self._citation_violation: bool = False
        self._citation_violation_id: str = ""
        self._citation_warning_emitted: bool = False
        self._stream_failed: bool = False
        self._is_closing: bool = False
        self._thread: QThread | None = None
        self._worker: _StreamWorker | None = None
        self._last_model_warning_key: str = ""

        # Active session (companion mode)
        from auranexus.core import ChatSession
        self._active_session: ChatSession = core.new_session()

        # Chat display options
        self._show_timestamps: bool = False
        self._scroll_to_bottom: bool = True
        self._streaming_enabled: bool = True
        self._rollback_retract_hirag: bool = False

        # world-state dialog flag — set True once the first dialog is shown
        self._world_state_dialog_shown: bool = False

        # TTS
        self._tts = TTSRouter()
        self._tts_espeak = EspeakProvider()  # kept for settings panel voice/speed/pitch compat
        self._tts_enabled: bool = True
        self._tts_thread: threading.Thread | None = None

        # STT
        self._recorder   = MicRecorder()
        self._transcriber: WhisperTranscriber | None = None  # lazy-init
        self._stt_enabled: bool = True
        self._stt_thread: QThread | None = None
        self._stt_worker: "_STTWorker | None" = None

        # Import Docs (Nexus Core KB ingestion)
        self._ingest_thread: "QThread | None" = None
        self._ingest_worker: "_IngestWorker | None" = None

        self.setWindowTitle("AuraNexus")
        self.resize(1100, 720)
        self.setMinimumSize(700, 480)

        self._apply_dark_theme()
        self._build_ui()
        self._load_settings()

        # Live status bar poll — checks Ollama's /api/ps every 15 s
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(15_000)
        self._status_timer.timeout.connect(self._poll_backend_status)
        self._status_timer.start()
        QTimer.singleShot(1500, self._poll_backend_status)

        # Thinking animation — pulses "..." while the AI is generating
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(450)
        self._thinking_timer.timeout.connect(self._tick_thinking_animation)
        self._thinking_dot_state: int = 0

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet("color: #333;")
        root.addWidget(div)

        # Centre — stacked by mode (companion / you'niverse)
        self._mode_stack = QWidget()
        stack_layout = QVBoxLayout(self._mode_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(0)

        self._companion_pane = self._build_companion_pane()
        self._youniverse_pane = self._build_youniverse_pane()
        self._youniverse_pane.setVisible(False)

        stack_layout.addWidget(self._companion_pane)
        stack_layout.addWidget(self._youniverse_pane)
        root.addWidget(self._mode_stack, stretch=1)

        # Settings drawer (hidden by default)
        self._settings_panel = SettingsPanel()
        self._settings_panel.setFixedWidth(320)
        self._settings_panel.setVisible(False)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        self._settings_panel.kb_refresh_requested.connect(self._refresh_kb_status)
        self._settings_panel.rag_import_requested.connect(self._handle_rag_import_request)
        root.addWidget(self._settings_panel)

        # Log drawer (hidden by default)
        self._log_panel = self._build_log_panel()
        self._log_panel.setVisible(False)
        root.addWidget(self._log_panel)

        # Memory panel (hidden by default)
        self._memory_panel = MemoryPanel()
        self._memory_panel.setVisible(False)
        root.addWidget(self._memory_panel)

        # Lorebook panel (hidden by default)
        self._lorebook_panel: LorebookPanel | None = None
        if self._core.lorebook is not None:
            self._lorebook_panel = LorebookPanel(self._core.lorebook)
            self._lorebook_panel.setFixedWidth(640)
            self._lorebook_panel.setVisible(False)
            self._lorebook_panel.lorebook_changed.connect(self._on_lorebook_changed)
            self._lorebook_panel.voice_preview_requested.connect(self._preview_persona_voice)
            root.addWidget(self._lorebook_panel)

        # WorldState panel (hidden by default; shown only in You'niverse mode)
        from auranexus.ui.world_state_panel import WorldStatePanel
        self._world_state_panel = WorldStatePanel(
            self._core._world_state,
            llm_fn=self._core._short_llm_call if hasattr(self._core, "_short_llm_call") else None,
        )
        self._world_state_panel.setFixedWidth(360)
        self._world_state_panel.setVisible(False)
        root.addWidget(self._world_state_panel)

        # Session list panel (hidden by default)
        self._session_panel = self._build_session_panel()
        self._session_panel.setVisible(False)
        root.addWidget(self._session_panel)

        # Knowledge panel (hidden by default) — tabbed Ingest + HiRAG Debug
        self._knowledge_panel = KnowledgePanel()
        self._knowledge_panel.setVisible(False)
        self._knowledge_panel.ingest_files_requested.connect(
            lambda paths: self._start_ingest(paths, f"{len(paths)} file(s)")
        )
        self._knowledge_panel.ingest_folder_requested.connect(
            lambda folder: self._start_ingest([folder], "folder")
        )
        self._knowledge_panel.remove_docs_requested.connect(self._remove_kb_docs)
        self._knowledge_panel.clear_kb_requested.connect(self._clear_kb)
        self._knowledge_panel.set_doc_section_requested.connect(self._set_doc_section)
        self._knowledge_panel.open_lore_dir_requested.connect(self._open_lore_dir)
        root.addWidget(self._knowledge_panel)

        # Writing canvas panel (hidden by default)
        self._canvas_panel = WritingCanvas()
        self._canvas_panel.setVisible(False)
        self._canvas_panel.set_rewrite_handler(self._core.rewrite_canvas_target)
        self._canvas_panel.status_message.connect(lambda msg: self.log(f"[canvas] {msg}"))
        root.addWidget(self._canvas_panel)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._provider_label = QLabel()
        self._status_bar.addPermanentWidget(self._provider_label)
        self._update_status()

        # Dev panel (only constructed when AURANEXUS_DEV=1)
        self._dev_panel = None
        if DEV_MODE:
            from auranexus.ui.dev_panel import DevPanel
            self._dev_panel = DevPanel()
            self._dev_panel.setVisible(False)
            root.addWidget(self._dev_panel)
            self._dev_panel.reset_first_run_requested.connect(lambda: None)  # handled inside panel
            self._dev_panel.clear_conversation_requested.connect(self._dev_clear_conversation)
            self._dev_panel.clear_emotional_memory_requested.connect(self._dev_clear_emotional)
            self._dev_panel.feedback_positive_requested.connect(
                lambda: self._dev_record_feedback(positive=True)
            )
            self._dev_panel.feedback_negative_requested.connect(
                lambda: self._dev_record_feedback(positive=False)
            )

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar.setObjectName("Sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(4)

        title = QLabel("AuraNexus")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setBold(True)
        f.setPointSize(13)
        title.setFont(f)
        title.setStyleSheet("color: #7a8fe8; padding: 8px 0;")
        layout.addWidget(title)

        if DEV_MODE:
            dev_btn = QPushButton("🛠 Dev")
            dev_btn.setToolTip("Toggle Developer Panel")
            dev_btn.setStyleSheet(
                "QPushButton { background:#3d1f1f; border:none; border-radius:4px;"
                " color:#f38ba8; font-size:11px; padding:3px 8px; margin:0 8px; }"
                "QPushButton:hover { background:#5a2828; }"
            )
            dev_btn.clicked.connect(self._toggle_dev_panel)
            layout.addWidget(dev_btn)

        layout.addSpacing(8)

        self._companion_btn = _SideButton("Companion")
        self._companion_btn.setChecked(True)
        self._companion_btn.clicked.connect(lambda: self._switch_mode("companion"))
        layout.addWidget(self._companion_btn)

        self._youniverse_btn = _SideButton("You'niverse")
        self._youniverse_btn.clicked.connect(lambda: self._switch_mode("youniverse"))
        layout.addWidget(self._youniverse_btn)

        layout.addStretch()

        self._chats_btn = _SideButton("Chats")
        self._chats_btn.clicked.connect(self._toggle_session_panel)
        layout.addWidget(self._chats_btn)

        self._log_btn = _SideButton("Log")
        self._log_btn.clicked.connect(self._toggle_log)
        layout.addWidget(self._log_btn)

        self._memory_btn = _SideButton("Memory")
        self._memory_btn.clicked.connect(self._toggle_memory)
        layout.addWidget(self._memory_btn)

        self._lorebook_btn = _SideButton("Lorebook")
        self._lorebook_btn.clicked.connect(self._toggle_lorebook)
        layout.addWidget(self._lorebook_btn)

        self._world_state_btn = _SideButton("World State")
        self._world_state_btn.clicked.connect(self._toggle_world_state)
        layout.addWidget(self._world_state_btn)

        self._settings_btn = _SideButton("Settings")
        self._settings_btn.clicked.connect(self._toggle_settings)
        layout.addWidget(self._settings_btn)

        self._knowledge_btn = _SideButton("Knowledge")
        self._knowledge_btn.clicked.connect(self._toggle_knowledge)
        layout.addWidget(self._knowledge_btn)

        self._canvas_btn = _SideButton("Canvas")
        self._canvas_btn.clicked.connect(self._toggle_canvas)
        layout.addWidget(self._canvas_btn)

        return sidebar

    def _build_session_panel(self) -> QWidget:
        """Slide-in panel listing saved chat sessions (like Gemini's sidebar)."""
        panel = QWidget()
        panel.setFixedWidth(210)
        panel.setObjectName("SessionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Chats")
        f = QFont()
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color:#cdd6f4;")
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("＋")
        new_btn.setFixedSize(26, 26)
        new_btn.setToolTip("New chat session")
        new_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:4px;"
            " color:#cdd6f4; font-size:14px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        new_btn.clicked.connect(self._new_session)
        header.addWidget(new_btn)
        layout.addLayout(header)

        # Session search / filter box
        self._session_filter = QLineEdit()
        self._session_filter.setPlaceholderText("Search sessions…")
        self._session_filter.setFixedHeight(24)
        self._session_filter.setClearButtonEnabled(True)
        self._session_filter.setStyleSheet(
            "QLineEdit { background:#1e1e2e; border:1px solid #313244; border-radius:4px;"
            " color:#cdd6f4; font-size:11px; padding:0 6px; }"
        )
        self._session_filter.textChanged.connect(self._filter_sessions)
        layout.addWidget(self._session_filter)

        self._session_list = QListWidget()
        self._session_list.setStyleSheet(
            "QListWidget { background:#181825; border:1px solid #313244;"
            " border-radius:4px; color:#cdd6f4; font-size:12px; }"
            "QListWidget::item { padding:5px 6px; border-radius:3px; }"
            "QListWidget::item:selected { background:#313244; color:#cdd6f4; }"
            "QListWidget::item:hover:!selected { background:#242436; }"
        )
        self._session_list.itemClicked.connect(self._on_session_clicked)
        layout.addWidget(self._session_list, stretch=1)

        del_btn = QPushButton("🗑 Delete")
        del_btn.setFixedHeight(26)
        del_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:4px;"
            " color:#f38ba8; font-size:11px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        del_btn.clicked.connect(self._delete_session)
        layout.addWidget(del_btn)

        self._refresh_session_list()
        return panel

    def _build_companion_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Persona portrait header (hidden when no active persona has an avatar)
        self._persona_header = QWidget()
        persona_header_row = QHBoxLayout(self._persona_header)
        persona_header_row.setContentsMargins(0, 0, 0, 4)
        persona_header_row.setSpacing(8)
        self._persona_avatar_label = QLabel()
        self._persona_avatar_label.setFixedSize(40, 40)
        self._persona_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._persona_avatar_label.setStyleSheet(
            "QLabel { background:#2a2a3d; border:1px solid #313244; border-radius:20px; }"
        )
        persona_header_row.addWidget(self._persona_avatar_label)
        self._persona_name_label = QLabel()
        self._persona_name_label.setStyleSheet("color:#cdd6f4; font-weight:bold; font-size:13px;")
        persona_header_row.addWidget(self._persona_name_label, stretch=1)
        self._persona_header.setVisible(False)
        layout.addWidget(self._persona_header)

        self._chat_view = ChatView()
        layout.addWidget(self._chat_view, stretch=1)

        # Thinking indicator — visible while the AI is generating
        self._thinking_label_companion = QLabel("")
        self._thinking_label_companion.setStyleSheet(
            "QLabel { color:#a6adc8; font-size:11px; font-style:italic; padding:1px 6px; }"
        )
        self._thinking_label_companion.setVisible(False)
        layout.addWidget(self._thinking_label_companion)

        # RAG source filter bar (collapsed by default, shown when RAG is ON)
        self._rag_filter_box = QPlainTextEdit()
        self._rag_filter_box.setPlaceholderText("RAG filter — type a filename keyword to limit sources (e.g. 1985, popular_electronics)…")
        self._rag_filter_box.setFixedHeight(28)
        self._rag_filter_box.setVisible(False)
        self._rag_filter_box.setStyleSheet(
            "QPlainTextEdit { background:#2a2a3d; color:#a6e3a1; border:1px solid #313244;"
            " border-radius:4px; font-size:11px; padding:2px 6px; }"
        )
        layout.addWidget(self._rag_filter_box)

        input_row = QHBoxLayout()

        # Mic button (push-to-talk)
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(40, 72)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setToolTip("Hold to record — release to transcribe")
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setStyleSheet(
            """
            QPushButton { background:#313244; border:none; border-radius:6px;
                          color:#cdd6f4; font-size:18px; }
            QPushButton:checked { background:#f38ba8; color:#1e1e2e; }
            QPushButton:hover:!checked { background:#45475a; }
            QPushButton:disabled { background:#222; color:#555; }
            """
        )
        self._mic_btn.pressed.connect(self._on_mic_pressed)
        self._mic_btn.released.connect(self._on_mic_released)
        input_row.addWidget(self._mic_btn)

        self._input_box = QPlainTextEdit()
        self._input_box.setPlaceholderText("Say something…")
        self._input_box.setFixedHeight(72)
        self._input_box.installEventFilter(self)
        input_row.addWidget(self._input_box)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedSize(72, 72)
        self._send_btn.clicked.connect(self._send_companion)
        self._send_btn.setStyleSheet(
            """
            QPushButton {
                background: #7a8fe8;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #8fa3f0; }
            QPushButton:disabled { background: #444; color: #888; }
            """
        )
        input_row.addWidget(self._send_btn)

        # RAG toggle button
        self._rag_btn = QPushButton("\U0001f4da")
        self._rag_btn.setFixedSize(36, 72)
        self._rag_btn.setCheckable(True)
        self._rag_btn.setChecked(True)
        self._rag_btn.setToolTip("Toggle RAG memory search (currently ON)")
        self._rag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rag_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:6px;"
            " color:#cdd6f4; font-size:18px; }"
            "QPushButton:checked { background:#a6e3a1; color:#1e1e2e; }"
            "QPushButton:hover:!checked { background:#45475a; }"
        )
        self._rag_btn.toggled.connect(self._on_rag_toggled)
        input_row.addWidget(self._rag_btn)

        # Save-to-RAG button — ingest current session turns into document KB
        self._save_rag_btn = QPushButton("⬆")
        self._save_rag_btn.setFixedSize(36, 72)
        self._save_rag_btn.setToolTip("Save this conversation to the knowledge base (RAG)")
        self._save_rag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_rag_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:6px;"
            " color:#cdd6f4; font-size:18px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        self._save_rag_btn.clicked.connect(self._save_session_to_rag)
        input_row.addWidget(self._save_rag_btn)

        # Stop-TTS button (hidden until Aura is speaking)
        self._stop_tts_btn = QPushButton("⏹")
        self._stop_tts_btn.setFixedSize(32, 72)
        self._stop_tts_btn.setToolTip("Stop Aura speaking")
        self._stop_tts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_tts_btn.setVisible(False)
        self._stop_tts_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:6px;"
            " color:#f38ba8; font-size:16px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        self._stop_tts_btn.clicked.connect(self._stop_tts)
        input_row.addWidget(self._stop_tts_btn)
        layout.addLayout(input_row)

        return pane

    def _build_youniverse_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Toolbar row ---
        toolbar = QHBoxLayout()

        new_btn = QPushButton("+ New Story")
        new_btn.setFixedHeight(30)
        new_btn.setStyleSheet(
            "QPushButton { background:#5b9e6f; border:none; border-radius:4px;"
            " color:white; font-weight:bold; padding:0 12px; }"
            "QPushButton:hover { background:#6db882; }"
        )
        new_btn.clicked.connect(self._open_new_scenario)
        toolbar.addWidget(new_btn)

        resume_btn = QPushButton("Resume")
        resume_btn.setFixedHeight(30)
        resume_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:4px;"
            " color:#cdd6f4; padding:0 12px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        resume_btn.clicked.connect(self._resume_scenario)
        toolbar.addWidget(resume_btn)

        toolbar.addStretch()
        self._story_title_label = QLabel("No story active")
        self._story_title_label.setStyleSheet("color:#a6adc8; font-style:italic; font-size:12px;")
        toolbar.addWidget(self._story_title_label)
        layout.addLayout(toolbar)

        # --- Story control bar ---
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(6)

        _ctrl_style = (
            "QPushButton { background:#313244; border:none; border-radius:4px;"
            " color:#cdd6f4; padding:2px 10px; font-size:12px; }"
            "QPushButton:hover { background:#45475a; }"
            "QPushButton:disabled { background:#1e1e2e; color:#585b70; }"
        )

        self._story_rewrite_btn = QPushButton("↺ Rewrite")
        self._story_rewrite_btn.setFixedHeight(26)
        self._story_rewrite_btn.setToolTip("Regenerate the last narrator response")
        self._story_rewrite_btn.setEnabled(False)
        self._story_rewrite_btn.setStyleSheet(_ctrl_style)
        self._story_rewrite_btn.clicked.connect(self._rewrite_last_beat)
        ctrl_bar.addWidget(self._story_rewrite_btn)

        self._story_rollback_btn = QPushButton("⟵ Rollback")
        self._story_rollback_btn.setFixedHeight(26)
        self._story_rollback_btn.setToolTip("Remove the last story beat entirely")
        self._story_rollback_btn.setEnabled(False)
        self._story_rollback_btn.setStyleSheet(_ctrl_style)
        self._story_rollback_btn.clicked.connect(self._rollback_last_beat)
        ctrl_bar.addWidget(self._story_rollback_btn)

        self._story_edit_btn = QPushButton("✎ Edit Response")
        self._story_edit_btn.setFixedHeight(26)
        self._story_edit_btn.setToolTip("Manually edit the last narrator response")
        self._story_edit_btn.setEnabled(False)
        self._story_edit_btn.setStyleSheet(_ctrl_style)
        self._story_edit_btn.clicked.connect(self._edit_last_beat)
        ctrl_bar.addWidget(self._story_edit_btn)

        ctrl_bar.addStretch()
        layout.addLayout(ctrl_bar)

        # --- Story view ---
        self._story_view = ChatView()
        layout.addWidget(self._story_view, stretch=1)

        # --- Context window usage bar ---
        ctx_row = QHBoxLayout()
        ctx_row.setContentsMargins(0, 0, 0, 0)
        self._ctx_label = QLabel("Context: —")
        self._ctx_label.setStyleSheet(
            "color:#585b70; font-size:10px; padding-left:4px;"
        )
        ctx_row.addWidget(self._ctx_label)
        ctx_row.addStretch()
        self._ctx_warn = QLabel("")
        self._ctx_warn.setStyleSheet("color:#f38ba8; font-size:10px; font-weight:bold;")
        ctx_row.addWidget(self._ctx_warn)
        layout.addLayout(ctx_row)

        # Thinking indicator — visible while the narrator AI is generating
        self._thinking_label_story = QLabel("")
        self._thinking_label_story.setStyleSheet(
            "QLabel { color:#a6adc8; font-size:11px; font-style:italic; padding:1px 6px; }"
        )
        self._thinking_label_story.setVisible(False)
        layout.addWidget(self._thinking_label_story)

        # --- Input row ---
        input_row = QHBoxLayout()

        # Story mic button (push-to-talk, mirrors companion pane)
        self._story_mic_btn = QPushButton("🎤")
        self._story_mic_btn.setFixedSize(40, 72)
        self._story_mic_btn.setToolTip("Hold to speak — release to transcribe")
        self._story_mic_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:6px;"
            " font-size:18px; }"
            "QPushButton:pressed { background:#585b70; }"
            "QPushButton:disabled { opacity:0.4; }"
        )
        self._story_mic_btn.pressed.connect(self._on_story_mic_pressed)
        self._story_mic_btn.released.connect(self._on_story_mic_released)
        input_row.addWidget(self._story_mic_btn)

        self._story_input = QPlainTextEdit()
        self._story_input.setPlaceholderText(
            "Describe what you do, or say something in character…"
        )
        self._story_input.setFixedHeight(72)
        self._story_input.installEventFilter(self)
        input_row.addWidget(self._story_input)

        # Action-type column — Say / Do / Story
        _action_btn_style = (
            "QPushButton {{ background:{bg}; border:none; border-radius:4px;"
            " color:white; font-size:11px; font-weight:bold; padding:0 6px; }}"
            "QPushButton:hover {{ background:{hv}; }}"
            "QPushButton:checked {{ background:{ck}; border:2px solid white; }}"
            "QPushButton:disabled {{ background:#444; color:#888; }}"
        )
        self._story_action_type: str = "do"   # "do" | "say" | "story"
        action_col = QVBoxLayout()
        action_col.setSpacing(3)

        self._story_do_btn = QPushButton("Do")
        self._story_do_btn.setFixedSize(52, 21)
        self._story_do_btn.setCheckable(True)
        self._story_do_btn.setChecked(True)
        self._story_do_btn.setToolTip("Describe a physical action — AI continues the story from there")
        self._story_do_btn.setStyleSheet(_action_btn_style.format(bg="#4a5568", hv="#5a6578", ck="#5b9e6f"))
        self._story_do_btn.clicked.connect(lambda: self._set_story_action_type("do"))

        self._story_say_btn = QPushButton("Say")
        self._story_say_btn.setFixedSize(52, 21)
        self._story_say_btn.setCheckable(True)
        self._story_say_btn.setToolTip("Write dialogue — AI shows your character speaking then continues")
        self._story_say_btn.setStyleSheet(_action_btn_style.format(bg="#4a5568", hv="#5a6578", ck="#5b9e6f"))
        self._story_say_btn.clicked.connect(lambda: self._set_story_action_type("say"))

        self._story_inject_btn = QPushButton("Story")
        self._story_inject_btn.setFixedSize(52, 21)
        self._story_inject_btn.setCheckable(True)
        self._story_inject_btn.setToolTip("Inject narrator text directly — your text becomes the next story beat as-is")
        self._story_inject_btn.setStyleSheet(_action_btn_style.format(bg="#4a5568", hv="#5a6578", ck="#6b4f8e"))
        self._story_inject_btn.clicked.connect(lambda: self._set_story_action_type("story"))

        action_col.addWidget(self._story_do_btn)
        action_col.addWidget(self._story_say_btn)
        action_col.addWidget(self._story_inject_btn)
        input_row.addLayout(action_col)

        self._story_send_btn = QPushButton("Continue")
        self._story_send_btn.setFixedSize(84, 72)
        self._story_send_btn.clicked.connect(self._send_story)
        self._story_send_btn.setStyleSheet(
            """
            QPushButton {
                background: #5b9e6f;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background: #6db882; }
            QPushButton:disabled { background: #444; color: #888; }
            """
        )
        input_row.addWidget(self._story_send_btn)
        layout.addLayout(input_row)

        return pane

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(360)
        panel.setObjectName("LogPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("Log")
        lbl.setStyleSheet("font-weight: bold; color: #a6adc8;")
        header.addWidget(lbl)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(
            "QPushButton { background:#313244; border:none; border-radius:3px; "
            "color:#a6adc8; padding:0 8px; font-size:11px; }"
            "QPushButton:hover { background:#45475a; }"
        )
        clear_btn.clicked.connect(lambda: self._log_view.clear())
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setObjectName("LogView")
        self._log_view.setStyleSheet(
            "QPlainTextEdit { background:#11111b; color:#a6e3a1; "
            "font-family: monospace; font-size: 11px; border:1px solid #313244; }"
        )
        layout.addWidget(self._log_view)

        return panel

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def log(self, msg: str) -> None:
        """Append a message to the log panel and print to stdout."""
        print(msg)
        self._log_view.appendPlainText(msg)
        self._log_view.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _switch_mode(self, mode: str) -> None:
        is_companion = mode == "companion"
        self._companion_pane.setVisible(is_companion)
        self._youniverse_pane.setVisible(not is_companion)
        self._companion_btn.setChecked(is_companion)
        self._youniverse_btn.setChecked(not is_companion)
        self._core.set_mode(mode)
        # Prompt for a scenario if switching to You'niverse with no active story
        if mode == "youniverse" and self._core.active_story is None:
            self._open_new_scenario()

    # ------------------------------------------------------------------
    # Scenario management
    # ------------------------------------------------------------------

    def _open_new_scenario(self) -> None:
        dlg = ScenarioDialog(
            narrator_name=self._core.aura_name,
            parent=self,
        )
        if dlg.exec() and dlg.session:
            self._core.active_story = dlg.session
            self._story_view.clear()
            self._story_title_label.setText(dlg.session.title)
            self.log(f"[Story started: {dlg.session.title}]")
            # Kick off the opening narration
            self._send_story_opening()

    def _resume_scenario(self) -> None:
        dlg = SavedScenariosDialog(parent=self)
        if dlg.exec() and dlg.chosen_id:
            try:
                from auranexus.story.session import StorySession
                session = StorySession.load(dlg.chosen_id)
                self._core.active_story = session
                self._core.set_mode("youniverse")
                self._story_view.clear()
                self._story_title_label.setText(session.title)
                # Replay beats into the view as flowing story
                for beat in session.beats:
                    if beat.player_action:
                        self._story_view.append_user(
                            session.player_name, beat.player_action
                        )
                    if beat.narrator_response:
                        self._story_view.start_assistant("")
                        self._story_view.close_assistant()
                        # Write the full narrator response directly
                        cursor = self._story_view.textCursor()
                        from PySide6.QtGui import QTextCursor  # noqa: PLC0415
                        cursor.movePosition(QTextCursor.MoveOperation.End)
                        cursor.insertText(
                            beat.narrator_response,
                            self._story_view._fmt("#c3e6cb"),  # noqa: SLF001
                        )
                        self._story_view.setTextCursor(cursor)
                        self._story_view.ensureCursorVisible()
                self._update_story_ctrl_buttons()
                self.log(f"[Story resumed: {session.title}, {len(session.beats)} beats]")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[ERROR loading story: {exc}]")

    def _send_story_opening(self) -> None:
        """Ask the narrator to set the scene — no player action yet."""
        story = self._core.active_story
        if story is None:
            return
        opening_prompt = (
            f"System: {story.build_system_prompt()}\n\n"
            f"Begin the story. Set the scene vividly. End at a moment that invites "
            f"{story.player_name} to act.\n\n"
            f"{story.narrator_name}:"
        )
        self._story_view.start_assistant(story.narrator_name, timestamp="")
        self._stream_raw(opening_prompt, self._story_view, opening=True)

    # ------------------------------------------------------------------
    # Settings / log drawer toggles
    # ------------------------------------------------------------------

    def _toggle_settings(self) -> None:
        visible = not self._settings_panel.isVisible()
        if visible:
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
        self._settings_panel.setVisible(visible)
        self._settings_btn.setChecked(visible)
        if visible:
            self._refresh_kb_status()

    def _toggle_knowledge(self) -> None:
        """Toggle the Knowledge panel (Ingest + HiRAG Debug)."""
        visible = not self._knowledge_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
        self._knowledge_panel.setVisible(visible)
        self._knowledge_btn.setChecked(visible)
        if visible:
            self._refresh_knowledge_panel()

    def _refresh_knowledge_panel(self, last_query: str = "") -> None:
        """Re-render the knowledge panel with current data."""
        try:
            kb_stats = self._core.kb_stats()
        except Exception:  # noqa: BLE001
            kb_stats = {"total_chunks": 0, "ingested_files": 0, "files": [],
                        "vector_search_available": False, "search_mode": "none"}
        self._knowledge_panel.refresh(
            kb_stats=kb_stats,
            simple_hirag=getattr(self._core, "_simple_hirag", None),
            chroma_hirag=getattr(self._core, "_hirag", None),
            last_query=last_query,
        )

    def _open_lore_dir(self) -> None:
        """Open the world_lore directory in the system file manager."""
        simple_hirag = getattr(self._core, "_simple_hirag", None)
        if simple_hirag is None:
            return
        lore_dir = str(getattr(simple_hirag, "lore_dir", ""))
        if not lore_dir:
            return
        import subprocess  # noqa: PLC0415
        import sys  # noqa: PLC0415
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", lore_dir])  # noqa: S603,S607
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", lore_dir])  # noqa: S603,S607
            else:
                subprocess.Popen(["xdg-open", lore_dir])  # noqa: S603,S607
        except Exception:  # noqa: BLE001
            QMessageBox.information(
                self,
                "World Lore Folder",
                f"Place plain-text lore files (.txt) in:\n{lore_dir}",
            )

    def _refresh_kb_status(self) -> None:
        """Refresh the Knowledge Base section in Settings (if available)."""
        try:
            stats = self._core.kb_stats()
        except Exception:  # noqa: BLE001
            stats = {
                "total_chunks": 0,
                "ingested_files": 0,
                "files": [],
                "vector_search_available": False,
                "search_mode": "none",
            }
        try:
            self._settings_panel.set_kb_status(stats)
        except Exception:  # noqa: BLE001
            pass

    @Slot()
    def _handle_rag_import_request(self) -> None:
        """Show a session picker and import the selected session into HiRAG."""
        sessions_dir = self._core.sessions_dir if hasattr(self._core, "sessions_dir") else None
        start_dir = str(sessions_dir) if sessions_dir else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a session file to import into HiRAG memory",
            start_dir,
            "JSON files (*.json)",
        )
        if not path:
            return
        import pathlib
        session_id = pathlib.Path(path).stem
        try:
            count = self._core.import_session_to_rag(session_id)
            QMessageBox.information(
                self,
                "Import complete",
                f"Imported {count} turn(s) from '{session_id}' into HiRAG memory.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Import failed",
                f"Could not import session '{session_id}':\n{exc}",
            )

    def _toggle_log(self) -> None:
        visible = not self._log_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
        self._log_panel.setVisible(visible)
        self._log_btn.setChecked(visible)
        if visible:
            self.log(f"[Log opened \u2014 backend: {self._core.provider_label}]")

    def _toggle_memory(self) -> None:
        visible = not self._memory_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
            self._memory_panel.refresh(self._core.emotional_memory, hirag=self._core._hirag)
        self._memory_panel.setVisible(visible)
        self._memory_btn.setChecked(visible)

    def _toggle_lorebook(self) -> None:
        if self._lorebook_panel is None:
            return
        visible = not self._lorebook_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
            self._lorebook_panel.refresh()
        self._lorebook_panel.setVisible(visible)
        self._lorebook_btn.setChecked(visible)

    def _toggle_world_state(self) -> None:
        visible = not self._world_state_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
            self._world_state_panel.refresh_table()
        self._world_state_panel.setVisible(visible)
        self._world_state_btn.setChecked(visible)

    def _toggle_canvas(self) -> None:
        visible = not self._canvas_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            if self._lorebook_panel is not None:
                self._lorebook_panel.setVisible(False)
                self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._session_panel.setVisible(False)
            self._chats_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
        self._canvas_panel.setVisible(visible)
        self._canvas_btn.setChecked(visible)

    def _on_lorebook_changed(self) -> None:
        """Called when the lorebook panel modifies personas or cards."""
        # Rebuild status bar to show active persona name if any
        self._update_status()
        # Refresh persona portrait in companion pane
        self._refresh_persona_portrait()

    def _refresh_persona_portrait(self) -> None:
        """Update the companion-pane avatar portrait to match the active persona."""
        lorebook = self._core.lorebook
        if lorebook is None:
            self._persona_header.setVisible(False)
            return
        try:
            persona = lorebook.active_persona()
        except Exception:  # noqa: BLE001
            persona = None

        if persona is None:
            self._persona_header.setVisible(False)
            return

        self._persona_name_label.setText(persona.name)
        avatar = getattr(persona, "avatar_path", None) or ""
        if avatar:
            from PySide6.QtGui import QPixmap
            pix = QPixmap(avatar)
            if not pix.isNull():
                self._persona_avatar_label.setPixmap(
                    pix.scaled(40, 40,
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
                )
            else:
                self._persona_avatar_label.setPixmap(QPixmap())
                self._persona_avatar_label.setText("?")
        else:
            self._persona_avatar_label.setPixmap(QPixmap())
            self._persona_avatar_label.setText("")
        self._persona_header.setVisible(True)

    def _preview_persona_voice(self, engine: str, voice_id: str) -> None:
        """Speak a short sample using the specified engine and voice."""
        sample = "Hello, I am ready to speak with you."
        try:
            from auranexus.tts.tts_router import TTSRouter
            router = TTSRouter(
                elevenlabs_api_key=self._tts._el_api_key,
                piper_model_path=self._tts._piper_model,
                coqui_model_name=self._tts._coqui_model,
            )
            # Build a minimal fake persona
            class _FakePersona:
                tts_engine = engine
                voice_id = voice_id or None
            threading.Thread(
                target=lambda: router.speak(sample, _FakePersona()),
                daemon=True,
            ).start()
        except Exception:  # noqa: BLE001
            pass

    @Slot(dict)
    def _on_settings_changed(self, s: dict) -> None:
        self._warn_on_model_fit_if_needed(s)
        self._core.apply_settings(s)
        self._update_status()
        self._save_settings(s)
        # TTS settings
        self._tts_enabled = s.get("tts_enabled", True)
        # Update TTSRouter with ElevenLabs key
        el_key = s.get("elevenlabs_key", "")
        self._tts.update_elevenlabs_key(el_key)
        # Update eSpeak fallback provider settings
        self._tts_espeak.voice = s.get("tts_voice", "en-us") or "en-us"
        self._tts_espeak.speed = int(s.get("tts_speed", 150))
        self._tts_espeak.pitch = int(s.get("tts_pitch", 50))
        # STT settings
        self._stt_enabled = s.get("stt_enabled", True)
        stt_model = s.get("stt_model", "base")
        if self._transcriber is not None and self._transcriber.model_size != stt_model:
            self._transcriber.model_size = stt_model
        self._mic_btn.setVisible(self._stt_enabled)
        # Chat display settings
        self._show_timestamps = s.get("show_timestamps", False)
        self._scroll_to_bottom = s.get("scroll_to_bottom", True)
        self._streaming_enabled = s.get("streaming_enabled", True)
        self._rollback_retract_hirag = s.get("rollback_retract_hirag", False)
        # RAG export toggle
        if hasattr(self._core, "rag_export_enabled"):
            self._core.rag_export_enabled = s.get("rag_export_enabled", True)

    def _warn_on_model_fit_if_needed(self, s: dict) -> None:
        """Show a hardware-fit warning when selected model likely exceeds capacity."""
        backend = str(s.get("backend", "ollama"))
        candidate = ""
        if backend == "ollama":
            candidate = str(s.get("ollama_model", "")).strip()
        elif backend == "llamacpp":
            candidate = str(s.get("gguf_path", "")).strip()

        if not candidate:
            return

        key = f"{backend}:{candidate}"
        if key == self._last_model_warning_key:
            return

        warning = build_fit_warning(candidate)
        self._last_model_warning_key = key
        if warning:
            QMessageBox.warning(self, "Hardware Optimization Warning", warning)

    @staticmethod
    def _now_ts() -> str:
        """Return current local time as 'HH:MM' for chat display."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M")

    # ------------------------------------------------------------------
    # Send actions
    # ------------------------------------------------------------------

    def _send_companion(self) -> None:
        text = self._input_box.toPlainText().strip()
        if not text or self._streaming:
            return

        # Security scan — check before sending to the LLM
        verdict, reasons = self._core.scan_input(text)
        if verdict == "blocked":
            QMessageBox.critical(
                self,
                "Message Blocked",
                "This message was blocked by the security scanner:\n\n• "
                + "\n• ".join(reasons),
            )
            return
        if verdict == "suspicious":
            detail = "\n• ".join(reasons)
            QMessageBox.warning(
                self,
                "Suspicious Content Blocked",
                "This message was blocked by the security scanner:\n\n• "
                + detail
                + "\n\nReview and revise the message before sending.",
            )
            return

        self._input_box.clear()
        user_name = self._core.user_name or "You"
        ts = self._now_ts() if self._show_timestamps else ""
        self._pending_ts = ts
        self._chat_view.append_user(user_name, text, timestamp=ts)
        self._chat_view.start_assistant(self._core.aura_name, timestamp=ts)
        self._stream(text, self._chat_view)

    def _set_story_action_type(self, mode: str) -> None:
        """Switch between 'do', 'say', 'story' input modes."""
        self._story_action_type = mode
        self._story_do_btn.setChecked(mode == "do")
        self._story_say_btn.setChecked(mode == "say")
        self._story_inject_btn.setChecked(mode == "story")
        placeholders = {
            "do":    "Describe what you do…  (AI writes the next beat)",
            "say":   "Write what you say…  (AI shows your speech and continues)",
            "story": "Write narrator text to inject directly into the story…",
        }
        self._story_input.setPlaceholderText(placeholders[mode])

    def _send_story(self) -> None:
        if self._core.active_story is None:
            self._open_new_scenario()
            return
        text = self._story_input.toPlainText().strip()
        if not text or self._streaming:
            return

        # Banned word/phrase check
        blocked, matched = self._core.check_story_input(text)
        if blocked:
            self._story_view.append_system(
                f"[Blocked: your message contains a banned word or phrase: \"{matched}\"]"
            )
            return

        self._story_input.clear()
        story = self._core.active_story
        ts = self._now_ts() if self._show_timestamps else ""
        self._pending_ts = ts
        action_mode = getattr(self, "_story_action_type", "do")

        # Apply story-script input processing
        if self._core.story_script_runner is not None:
            text = self._core.story_script_runner.process_input(text)
            if not text:
                self._story_view.append_system("[Story script returned empty input — nothing was sent.]")
                return

        if action_mode == "story":
            # Direct injection: the user's text becomes the next narrator beat as-is.
            # Show it in the story view as plain narration (no player label).
            # post_turn() adds the beat and saves it, so we only need the display call here.
            self._story_view.append_system(text)
            self._core.post_turn("", text, ts)
            self._update_story_ctrl_buttons()
            self._notify_world_state_beat(text)
            return

        if action_mode == "say":
            # Show the player's speech with a subtle inline label, then let AI continue.
            display_text = f'"{text}"'
            self._story_view.append_user(story.player_name, display_text, timestamp=ts)
            # Build a prompt that frames it as spoken dialogue
            prompt_action = f'{story.player_name} says: "{text}"'
        else:
            # "do" mode — physical action
            self._story_view.append_user(story.player_name, text, timestamp=ts)
            prompt_action = text

        self._story_view.start_assistant(story.narrator_name, timestamp=ts)
        self._stream(prompt_action, self._story_view)

    def _update_story_ctrl_buttons(self) -> None:
        """Enable/disable story control buttons based on whether there are any beats."""
        has_beats = (
            self._core.active_story is not None
            and len(self._core.active_story.beats) > 0
        )
        self._story_rewrite_btn.setEnabled(has_beats and not self._streaming)
        self._story_rollback_btn.setEnabled(has_beats and not self._streaming)
        self._story_edit_btn.setEnabled(has_beats and not self._streaming)

    def _notify_world_state_beat(self, beat_text: str) -> None:
        """Feed a new beat to the WorldState panel, showing the turn dialog if first trigger."""
        if not beat_text:
            return
        # First time reaching the review interval threshold? Show the dialog.
        if not self._world_state_dialog_shown:
            pending_count = getattr(self._world_state_panel, "_turn_counter", 0) + 1
            if pending_count >= self._world_state_panel._review_interval:
                from auranexus.ui.world_state_turn_dialog import WorldStateTurnDialog
                interval, suppressed = WorldStateTurnDialog.maybe_show(
                    self._world_state_panel._review_interval, self
                )
                self._world_state_panel.set_review_interval(interval)
                self._world_state_dialog_shown = suppressed
        # Set story title
        if self._core.active_story is not None:
            self._world_state_panel.set_story_title(self._core.active_story.title)
        self._world_state_panel.set_llm_fn(self._core._short_llm_call)
        self._world_state_panel.add_beat(beat_text)

    @Slot()
    def _rewrite_last_beat(self) -> None:
        """Remove the last beat from the session and regenerate the narrator response."""
        if self._core.active_story is None or self._streaming:
            return
        if not self._core.active_story.beats:
            return
        last_beat = self._core.active_story.rollback_last_beat()
        if last_beat is None:
            return
        # Remove the last two chat bubbles (user + assistant) then regenerate
        self._story_view.remove_last_exchange()
        self._update_story_ctrl_buttons()
        # Re-send with the same player action (if there was one)
        if last_beat.player_action:
            self._story_view.append_user(
                self._core.active_story.player_name, last_beat.player_action
            )
            self._story_view.start_assistant(self._core.active_story.narrator_name)
            self._stream(last_beat.player_action, self._story_view)

    @Slot()
    def _rollback_last_beat(self) -> None:
        """Remove the last story beat entirely."""
        if self._core.active_story is None or self._streaming:
            return
        beat = self._core.active_story.rollback_last_beat()
        if beat is None:
            return
        if self._rollback_retract_hirag and beat.player_action:
            # Retract the HiRAG turn using the story's own session_id so the
            # correct per-story memory entry is targeted, not the Companion
            # session that self._core._session_id represents.
            try:
                if self._core._hirag is not None:
                    self._core._hirag.retract_last_turn(
                        self._core.active_story.session_id
                    )
            except Exception:  # noqa: BLE001
                pass
        self._story_view.remove_last_exchange()
        try:
            self._core.active_story.save()
        except OSError:
            pass
        self._update_story_ctrl_buttons()

    @Slot()
    def _edit_last_beat(self) -> None:
        """Let the user manually edit the last narrator response."""
        if self._core.active_story is None or self._streaming:
            return
        beats = self._core.active_story.beats
        if not beats:
            return
        if not _EditWarningDialog.maybe_show(self):
            return
        last_idx = len(beats) - 1
        current_text = beats[last_idx].narrator_response
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Edit Response", "Narrator response:", current_text
        )
        if ok and new_text.strip():
            self._core.active_story.edit_beat(last_idx, new_text.strip())
            self._story_view.replace_last_narrator_content(new_text.strip())
            try:
                self._core.active_story.save()
            except OSError:
                pass

    def _stream(self, user_text: str, view: ChatView) -> None:
        rag_filter = self._rag_filter_box.toPlainText().strip()
        self._stream_raw(
            self._core.build_prompt(user_text, rag=self._core.rag_enabled, rag_filter=rag_filter),
            view,
            user_text=user_text,
        )

    def _stream_raw(
        self,
        prompt: str,
        view: ChatView,
        user_text: str = "",
        opening: bool = False,
    ) -> None:
        self._streaming = True
        self._accumulated_response = ""
        self._active_view = view
        self._stream_is_opening = opening
        self._citation_violation = False
        self._citation_violation_id = ""
        self._citation_warning_emitted = False
        self._stream_failed = False
        active_source_ids = self._core.get_active_source_ids()
        self._citation_manager.begin_turn(active_source_ids)
        self._send_btn.setText("\u25a0 Stop")
        self._send_btn.clicked.disconnect()
        self._send_btn.clicked.connect(self._stop_generation)
        self._send_btn.setEnabled(True)
        # In You'niverse mode also convert the story send button to a Stop button
        if self._core._mode == "youniverse":
            self._story_send_btn.setText("\u25a0 Stop")
            try:
                self._story_send_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._story_send_btn.clicked.connect(self._stop_generation)
            self._story_send_btn.setEnabled(True)
        else:
            self._story_send_btn.setEnabled(False)
        self._pending_user_message = user_text
        # `prompt` is already built by the caller — use it directly
        self.log(f"[>> sending to {self._core.provider_label}]")

        # Show the animated thinking indicator while waiting for the first token
        self._thinking_dot_state = 0
        if self._core._mode == "youniverse":
            self._thinking_label_story.setText("✦ Narrator is writing")
            self._thinking_label_story.setVisible(True)
        else:
            name = self._core.aura_name or "Aura"
            self._thinking_label_companion.setText(f"✦ {name} is thinking")
            self._thinking_label_companion.setVisible(True)
        self._thinking_timer.start()

        self._thread = QThread()
        self._worker = _StreamWorker(self._core.provider, prompt)
        self._worker.moveToThread(self._thread)

        # Connect to named @Slot methods on MainWindow (which lives in the main
        # thread) so Qt uses QueuedConnection automatically.  Lambdas have no
        # thread affinity and get DirectConnection — causing wait-on-itself crash.
        self._thread.started.connect(self._worker.run)
        self._worker.token_received.connect(self._accumulate_token)
        self._worker.stream_done.connect(self._on_stream_done)
        self._worker.error_occurred.connect(self._on_stream_error)
        # Qt will destroy the C++ objects once finished; _on_thread_finished
        # nulls our Python references AFTER the thread has truly stopped.
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    def _restore_send_buttons(self) -> None:
        """Restore Send/Continue buttons after generation ends or is stopped."""
        self._send_btn.setText("Send")
        try:
            self._send_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._send_btn.clicked.connect(self._send_companion)
        self._send_btn.setEnabled(True)
        self._story_send_btn.setText("Continue")
        try:
            self._story_send_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._story_send_btn.clicked.connect(self._send_story)
        self._story_send_btn.setEnabled(True)
        # Hide the thinking indicator
        self._thinking_timer.stop()
        self._thinking_label_story.setVisible(False)
        self._thinking_label_companion.setVisible(False)

    @Slot()
    def _stop_generation(self) -> None:
        """Interrupt the current streaming response."""
        if self._worker is not None:
            self._worker.request_stop()
        # Restore buttons immediately so the user isn't stuck
        self._restore_send_buttons()

    @Slot()
    def _tick_thinking_animation(self) -> None:
        """Advance the animated thinking indicator by one dot-cycle step."""
        dots = "." * self._thinking_dot_state
        self._thinking_dot_state = (self._thinking_dot_state + 1) % 4
        if self._core._mode == "youniverse":
            self._thinking_label_story.setText(f"✦ Narrator is writing{dots}")
        else:
            name = self._core.aura_name or "Aura"
            self._thinking_label_companion.setText(f"✦ {name} is thinking{dots}")

    @Slot(bool)
    def _on_rag_toggled(self, checked: bool) -> None:
        self._core.rag_enabled = checked
        tooltip = "Toggle RAG memory search (currently ON)" if checked else "Toggle RAG memory search (currently OFF)"
        self._rag_btn.setToolTip(tooltip)
        self._rag_filter_box.setVisible(checked)

    @Slot(str)
    def _accumulate_token(self, token: str) -> None:
        if self._citation_violation:
            return

        inspected = self._citation_manager.inspect_token(token)
        safe_fragment = inspected.safe_text
        if safe_fragment:
            self._accumulated_response += safe_fragment
            if self._active_view:
                self._active_view.stream_token(safe_fragment)

        if inspected.violation:
            self._citation_violation = True
            self._citation_violation_id = inspected.bad_id
            if self._worker is not None:
                self._worker.request_stop()

            # Ensure any partially streamed assistant bubble only keeps
            # verified output that occurred before the violating marker.
            if self._active_view:
                self._active_view.replace_last_assistant_content(self._accumulated_response)

            if not self._citation_warning_emitted and self._active_view:
                self._active_view.append_system(
                    "[CRITICAL: Citation Contract Violation - Generation Terminated due to Unverified Source Lore]"
                )
                self._citation_warning_emitted = True

        # Once the first token arrives the response is visibly streaming — hide
        # the thinking indicator so it doesn't overlap with the generated text.
        if self._thinking_timer.isActive():
            self._thinking_timer.stop()
            self._thinking_label_story.setVisible(False)
            self._thinking_label_companion.setVisible(False)

    @Slot()
    def _on_thread_finished(self) -> None:
        """Null Python refs AFTER the thread has fully stopped — safe to GC now.

        Guard by identity: if a new thread was already started (e.g. tool
        follow-up re-stream), the old thread's finished signal must NOT wipe
        the new thread's references.
        """
        finished_thread = self.sender()
        if self._thread is finished_thread:
            self._thread = None
            self._worker = None

    def _cleanup_thread(self) -> None:
        """Stop the stream thread deterministically.

        We only block with wait() when called from a different thread than the
        worker thread to avoid self-wait deadlocks.
        """
        if self._thread is None:
            return

        thr = self._thread
        if not thr.isRunning():
            return

        thr.quit()

        # Deterministic teardown: wait for graceful exit when safe.
        # If called from the worker thread itself, waiting would deadlock.
        if QThread.currentThread() is thr:
            return

        # Keep UI responsive while waiting for shutdown by polling in short
        # slices and processing events between checks.
        deadline_ms = 5000  # P21: allow up to 5s graceful worker teardown
        slice_ms = 25
        elapsed = 0
        while thr.isRunning() and elapsed < deadline_ms:
            thr.wait(slice_ms)
            app = QCoreApplication.instance()
            if app is not None:
                app.processEvents()
            elapsed += slice_ms

        if thr.isRunning():
            # Last-resort hard stop if the worker does not unwind in time.
            thr.terminate()
            thr.wait(250)

    @Slot()
    def _on_stream_done(self) -> None:
        # Terminal-state guard: if error handler has already fired for this
        # turn, do not run normal completion/persistence flow.
        if self._stream_failed:
            self._cleanup_thread()
            self._streaming = False
            self._restore_send_buttons()
            return

        if not self._citation_violation:
            tail = self._citation_manager.flush()
            if tail:
                self._accumulated_response += tail
                if self._active_view:
                    self._active_view.stream_token(tail)

        full_response = self._accumulated_response.strip()

        if self._citation_violation:
            try:
                if self._active_view:
                    self._active_view.replace_last_assistant_content(full_response)
                    self._active_view.close_assistant()
                    if not self._citation_warning_emitted:
                        self._active_view.append_system(
                            "[CRITICAL: Citation Contract Violation - Generation Terminated due to Unverified Source Lore]"
                        )
                        self._citation_warning_emitted = True
                self.log(
                    "[security: citation-contract violation — "
                    f"unverified_id={self._citation_violation_id or 'unknown'}]"
                )
            finally:
                self._cleanup_thread()
                self._streaming = False
                self._restore_send_buttons()
            return

        # Actions: intercept tool calls in Companion mode only
        if self._core._mode == "companion" and full_response:
            from auranexus.actions.parser import parse_tool_calls, strip_tool_calls
            tool_calls = parse_tool_calls(full_response)
            if tool_calls:
                display = strip_tool_calls(full_response).strip()
                if self._active_view:
                    self._active_view.replace_last_assistant_content(display)
                    self._active_view.close_assistant()
                if len(tool_calls) > 1:
                    # Reject multi-call responses explicitly so there is no
                    # silent discrepancy between what the model claimed to do
                    # and what actually executed.
                    self.log(f"[tool: {len(tool_calls)} calls in one response — only one allowed; rejecting]")
                    if self._active_view:
                        self._active_view.append_system(
                            f"[{len(tool_calls)} tool calls were requested at once. "
                            "Please request one action at a time.]"
                        )
                    self._core.post_turn(self._pending_user_message, display, self._pending_ts)
                    self._persist_active_session()
                    self._streaming = False
                    self._restore_send_buttons()
                    return
                self._handle_tool_call(tool_calls[0], display)
                return  # tool flow takes it from here

        try:
            # Story-script output processing (You'niverse mode)
            if self._core._mode == "youniverse" and self._core.story_script_runner is not None:
                processed = self._core.story_script_runner.process_output(full_response)
                if processed != full_response:
                    if self._active_view:
                        self._active_view.replace_last_assistant_content(processed)
                    full_response = processed

            # Normal path
            if self._active_view:
                self._active_view.close_assistant()
            self.log(f"[response: {len(full_response)} chars]")
            # Show a hint when the narrator produces no text at all (e.g. LLM not
            # configured, empty generation, or a race with a rapid stop request).
            if not full_response and self._core._mode == "youniverse":
                if self._active_view:
                    self._active_view.append_system(
                        "[Narrator returned no text — check your LLM connection and try again.]"
                    )
            if self._stream_is_opening:
                # Opening narration: store as a beat with empty player action
                if self._core.active_story is not None:
                    self._core.active_story.add_beat("", full_response)
                    try:
                        self._core.active_story.save()
                    except OSError:
                        pass
                self._update_story_ctrl_buttons()
                try:
                    self._notify_world_state_beat(full_response)
                except Exception:  # noqa: BLE001
                    pass
            else:
                self._core.post_turn(self._pending_user_message, full_response, self._pending_ts)
                if self._core._mode == "youniverse":
                    self._update_story_ctrl_buttons()
                    try:
                        self._notify_world_state_beat(full_response)
                    except Exception:  # noqa: BLE001
                        pass
                if self._core._mode == "companion":
                    self._persist_active_session()
        finally:
            # Always reset streaming state so the UI is never stuck
            self._cleanup_thread()
            self._streaming = False
            self._restore_send_buttons()

        # Update context usage indicator (You'niverse mode)
        if self._core._mode == "youniverse" and self._core.active_story is not None:
            try:
                story = self._core.active_story
                ctx_chars = len(story.build_system_prompt()) + len(story.build_context_window(max_beats=20))
                ctx_tokens = ctx_chars // 4
                budget = self._core._PROMPT_TOKEN_BUDGET
                pct = min(ctx_tokens / max(budget, 1) * 100, 100)
                self._ctx_label.setText(f"Context: ~{ctx_tokens:,} / {budget:,} tokens  ({pct:.0f}%)")
                if pct >= 90:
                    self._ctx_warn.setText("⚠ Context nearly full")
                elif pct >= 75:
                    self._ctx_warn.setText("Context filling up")
                else:
                    self._ctx_warn.setText("")
            except Exception:  # noqa: BLE001
                pass
        if self._memory_panel.isVisible():
            self._memory_panel.refresh(self._core.emotional_memory, hirag=self._core._hirag)
        if self._knowledge_panel.isVisible():
            self._refresh_knowledge_panel(last_query=self._pending_user_message)
        # Dev panel: update with last prompt and RAG chunk info
        if self._dev_panel is not None and DEV_MODE:
            try:
                last_prompt = self._core.build_prompt(self._pending_user_message)
            except Exception:
                last_prompt = ""
            ds = getattr(self._core, "_doc_store", None)
            rag_titles: list[str] = []
            rag_chunk_ids: list[str] = []
            if ds is not None and self._pending_user_message:
                try:
                    results = ds.retrieve(self._pending_user_message, top_k=4)
                    rag_chunk_ids = [r["chunk_id"] for r in results]
                    rag_titles    = [r["title"] for r in results]
                except Exception:
                    pass
            self._dev_panel.update_after_turn(
                prompt=last_prompt,
                rag_chunk_ids=rag_chunk_ids,
                rag_titles=rag_titles,
            )

        # TTS: speak Aura's response (strip tool blocks first)
        if self._tts_enabled and self._tts.available:
            from auranexus.actions.parser import strip_tool_calls
            speak_text = strip_tool_calls(full_response).strip()
            if speak_text:
                self._speak(speak_text)

    def _handle_tool_call(self, req, display_response: str) -> None:
        """Show confirmation dialog; if accepted run the action and re-stream."""
        from auranexus.actions.executor import execute
        from auranexus.ui.confirmation_dialog import ConfirmationDialog
        from PySide6.QtWidgets import QDialog

        self._cleanup_thread()  # stop the old streaming thread

        # Pre-scan code actions so warnings appear in the dialog.
        # BLOCKED code is refused before the dialog even opens.
        scan_warnings: list[str] = []
        if req.action == "run_python":
            try:
                from security.scanner import ContentScanner, Verdict
                code_text = req.params.get("code", "")
                code_hash = hashlib.sha256(code_text.encode("utf-8")).hexdigest()
                approvals_path = (
                    Path.home()
                    / ".local"
                    / "share"
                    / "auranexus"
                    / "security"
                    / "approved_script_hashes.json"
                )
                approved_hashes: set[str] = set()
                try:
                    if approvals_path.exists():
                        data = json.loads(approvals_path.read_text(encoding="utf-8"))
                        hashes = data.get("approved_hashes", []) if isinstance(data, dict) else []
                        if isinstance(hashes, list):
                            approved_hashes = {
                                str(h).strip().lower() for h in hashes if str(h).strip()
                            }
                except Exception:  # noqa: BLE001
                    approved_hashes = set()

                scan = ContentScanner().scan_code(code_text)
                if scan.verdict == Verdict.BLOCKED:
                    reasons_text = "\n".join(f"• {r}" for r in scan.reasons)
                    if self._active_view:
                        self._active_view.append_system(
                            f"[Security: code blocked before execution]\n{reasons_text}"
                        )
                    self.log(f"[security: run_python blocked — {scan.reasons[0]}]")
                    self._streaming = False
                    self._restore_send_buttons()
                    return
                if scan.verdict == Verdict.SUSPICIOUS and code_hash.lower() not in approved_hashes:
                    reasons_text = "\n".join(f"- {r}" for r in scan.reasons)
                    if self._active_view:
                        self._active_view.append_system(
                            "[Security: suspicious code blocked before execution]\n"
                            f"SHA256: {code_hash}\n"
                            "Add this hash to approved_script_hashes.json to allow it:\n"
                            f"{reasons_text}"
                        )
                    self.log(
                        "[security: run_python suspicious-blocked — "
                        f"hash={code_hash} reason={scan.reasons[0] if scan.reasons else 'unspecified'}]"
                    )
                    self._streaming = False
                    self._restore_send_buttons()
                    return
                scan_warnings = scan.reasons
            except ImportError:
                pass

        dlg = ConfirmationDialog(req, parent=self, scan_warnings=scan_warnings)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted

        if accepted:
            result = execute(req)
            status = "\u2713" if result.ok else "\u2717"
            snippet = result.output[:300] + ("\u2026" if len(result.output) > 300 else "")
            if self._active_view:
                self._active_view.append_system(
                    f"[{req.action} {status}]\n{snippet}"
                )
            self.log(f"[tool {req.action}: {'ok' if result.ok else 'error'}]")

            follow_up = self._core.build_tool_follow_up_prompt(
                self._pending_user_message,
                display_response,
                result.as_context_block(),
            )
            original_user = self._pending_user_message
            view = self._active_view or self._chat_view
            view.start_assistant(self._core.aura_name)
            self._stream_raw(follow_up, view)
            # _stream_raw overwrites _pending_user_message with ""; restore it
            # so the eventual post_turn() gets the original user text.
            self._pending_user_message = original_user
        else:
            if self._active_view:
                self._active_view.append_system("[Action denied]")
            self.log(f"[tool {req.action}: denied by user]")
            self._core.post_turn(self._pending_user_message, display_response, self._pending_ts)
            self._persist_active_session()
            self._streaming = False
            self._restore_send_buttons()
            if self._memory_panel.isVisible():
                self._memory_panel.refresh(self._core.emotional_memory, hirag=self._core._hirag)
            if self._knowledge_panel.isVisible():
                self._refresh_knowledge_panel(last_query=self._pending_user_message)

    @Slot(str)
    def _on_stream_error(self, error: str) -> None:
        self._stream_failed = True
        if self._active_view:
            self._active_view.close_assistant()
            self._active_view.append_system(f"[Error: {error}]")
        self.log(f"[ERROR] {error}")
        self._cleanup_thread()
        self._streaming = False
        self._restore_send_buttons()

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def _speak(self, text: str, persona=None) -> None:
        """Route TTS via TTSRouter using the active persona's voice settings."""
        self._tts.stop()
        if self._tts_thread and self._tts_thread.is_alive():
            self._tts_thread.join(timeout=0.2)

        self._stop_tts_btn.setVisible(True)

        # Resolve persona: use provided or try to get the active lorebook persona
        if persona is None and self._core.lorebook is not None:
            try:
                active_personas = [
                    p for p in self._core.lorebook.personas if p.is_active
                ]
                if active_personas:
                    persona = active_personas[0]
            except Exception:  # noqa: BLE001
                pass

        def _run() -> None:
            self._tts.speak(text, persona=persona)
            from PySide6.QtCore import QMetaObject, Qt as _Qt
            QMetaObject.invokeMethod(
                self._stop_tts_btn, "hide",
                _Qt.ConnectionType.QueuedConnection,
            )

        self._tts_thread = threading.Thread(target=_run, daemon=True)
        self._tts_thread.start()

    def _stop_tts(self) -> None:
        self._tts.stop()
        self._stop_tts_btn.setVisible(False)

    # ------------------------------------------------------------------
    # STT — push-to-talk mic button
    # ------------------------------------------------------------------

    def _on_mic_pressed(self) -> None:
        """Start recording when the mic button is pressed."""
        if not self._stt_enabled:
            return
        self._stop_tts()           # stop Aura if speaking
        self._recorder.start_recording()
        self.log("[STT: recording…]")

    def _on_mic_released(self) -> None:
        """Stop recording and transcribe in a background thread."""
        if not self._stt_enabled or not self._recorder.is_recording:
            return
        audio = self._recorder.stop_recording()
        if audio is None or len(audio) == 0:
            return
        self.log(f"[STT: captured {len(audio)/16000:.1f}s]")
        self._mic_btn.setEnabled(False)
        self._run_transcription(audio)

    def _on_story_mic_pressed(self) -> None:
        """Start recording when the story mic button is pressed (You'niverse pane)."""
        if not self._stt_enabled:
            return
        self._stop_tts()
        self._recorder.start_recording()
        self.log("[STT story: recording…]")

    def _on_story_mic_released(self) -> None:
        """Stop recording and transcribe; result routes to story input box."""
        if not self._stt_enabled or not self._recorder.is_recording:
            return
        audio = self._recorder.stop_recording()
        if audio is None or len(audio) == 0:
            return
        self.log(f"[STT story: captured {len(audio)/16000:.1f}s]")
        self._story_mic_btn.setEnabled(False)
        self._run_transcription(audio)

    def _run_transcription(self, audio) -> None:
        """Transcribe audio in a QThread so the UI stays responsive."""
        # Guard: if a transcription is already running, discard this audio
        # rather than overwriting self._stt_thread and leaking the old one.
        if self._stt_thread is not None:
            return
        if self._transcriber is None:
            from auranexus.stt.transcriber import WhisperTranscriber
            self._transcriber = WhisperTranscriber()

        self._stt_thread  = QThread()
        self._stt_worker  = _STTWorker(self._transcriber, audio)
        self._stt_worker.moveToThread(self._stt_thread)
        self._stt_thread.started.connect(self._stt_worker.run)
        self._stt_worker.transcription_done.connect(self._on_transcription)
        self._stt_worker.transcription_done.connect(self._stt_thread.quit)
        self._stt_thread.finished.connect(self._stt_worker.deleteLater)
        self._stt_thread.finished.connect(self._stt_thread.deleteLater)
        self._stt_thread.finished.connect(self._on_stt_thread_finished)
        self._stt_thread.start()

    @Slot(str)
    def _on_transcription(self, text: str) -> None:
        """Insert transcribed text into the active input box (mode-aware)."""
        self.log(f"[STT: '{text}']")
        if not text:
            return
        # Route to the correct input box depending on which mode is active
        target = (
            self._story_input
            if self._core._mode == "youniverse"
            else self._input_box
        )
        current = target.toPlainText()
        sep = " " if current and not current.endswith(" ") else ""
        target.setPlainText(current + sep + text)
        # Move cursor to end
        cursor = target.textCursor()
        from PySide6.QtGui import QTextCursor as _TC
        cursor.movePosition(_TC.MoveOperation.End)
        target.setTextCursor(cursor)

    @Slot()
    def _on_stt_thread_finished(self) -> None:
        self._stt_thread = None
        self._stt_worker = None
        self._mic_btn.setEnabled(True)
        self._story_mic_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Document ingestion (triggered from KnowledgePanel signals)
    # ------------------------------------------------------------------

    def _start_ingest(self, paths: list[str], label: str) -> None:
        if self._ingest_thread is not None:
            return

        self._knowledge_panel.set_ingest_running(True)
        self.statusBar().showMessage(f"Ingesting {label}…")

        self._ingest_worker = _IngestWorker(self._core, paths)
        self._ingest_thread = QThread(self)
        self._ingest_worker.moveToThread(self._ingest_thread)
        self._ingest_thread.started.connect(self._ingest_worker.run)
        self._ingest_worker.progress.connect(self.statusBar().showMessage)
        self._ingest_worker.done.connect(self._on_ingest_done)
        self._ingest_thread.finished.connect(self._on_ingest_thread_finished)
        self._ingest_thread.start()

    @Slot(list)
    def _remove_kb_docs(self, doc_ids: list[str]) -> None:
        if self._core._doc_store is None:
            return
        removed = self._core._doc_store.remove_docs(doc_ids)
        msg = f"KB: removed {removed} document(s)"
        self.statusBar().showMessage(msg, 6000)
        self.log(f"[KB] {msg}")
        self._refresh_knowledge_panel()

    @Slot()
    def _clear_kb(self) -> None:
        removed = self._core.clear_knowledge_base()
        msg = f"KB: cleared {removed} document(s)"
        self.statusBar().showMessage(msg, 6000)
        self.log(f"[KB] {msg}")
        self._refresh_knowledge_panel()

    @Slot(str, str)
    def _set_doc_section(self, doc_id: str, section: str) -> None:
        ok = self._core.set_doc_section(doc_id, section)
        if ok:
            label = "personal (assistant only)" if section == "assistant" else "shared"
            self.statusBar().showMessage(f"KB: document marked as {label}", 4000)
        self._refresh_knowledge_panel()

    # ------------------------------------------------------------------
    # Dev mode helpers
    # ------------------------------------------------------------------

    def _toggle_dev_panel(self) -> None:
        if self._dev_panel is None:
            return
        self._dev_panel.setVisible(not self._dev_panel.isVisible())

    @Slot()
    def _dev_clear_conversation(self) -> None:
        self._core._recent_turns.clear()
        self._core._turn_timestamps.clear()
        self.statusBar().showMessage("Dev: conversation history cleared", 4000)

    @Slot()
    def _dev_clear_emotional(self) -> None:
        try:
            em = self._core.emotional_memory
            em._mood_history.clear()  # type: ignore[attr-defined]
            em._save()                # type: ignore[attr-defined]
        except Exception:
            pass
        self.statusBar().showMessage("Dev: emotional memory reset", 4000)

    def _dev_record_feedback(self, positive: bool) -> None:
        ds = getattr(self._core, "_doc_store", None)
        if ds is None or not hasattr(self._dev_panel, "_last_chunk_id"):
            return
        chunk_id = self._dev_panel._last_chunk_id  # type: ignore[union-attr]
        if not chunk_id:
            self.statusBar().showMessage("Dev: no RAG chunk to rate yet", 3000)
            return
        try:
            ds.record_feedback(chunk_id, positive=positive)
            label = "👍 positive" if positive else "👎 negative"
            self.statusBar().showMessage(f"Dev: feedback recorded ({label})", 4000)
        except Exception as exc:
            self.statusBar().showMessage(f"Dev: feedback error — {exc}", 4000)

    @Slot(list)
    def _on_ingest_done(self, results: list[dict]) -> None:
        ok = sum(1 for r in results if r.get("status") == "ok")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        errors = sum(1 for r in results if r.get("status") == "error")
        total_chunks = sum(r.get("chunks_created", 0) for r in results)

        parts = []
        if ok:
            parts.append(f"{ok} ingested ({total_chunks} chunks)")
        if skipped:
            parts.append(f"{skipped} skipped")
        if errors:
            parts.append(f"{errors} error(s)")

        msg = "KB: " + ", ".join(parts) if parts else "KB: nothing to do"
        self.statusBar().showMessage(msg, 8000)
        self.log(f"[Import] {msg}")
        for r in results:
            self.log(f"  {r.get('filename','')} → {r.get('message','')}")

        if self._settings_panel.isVisible():
            self._refresh_kb_status()
        if self._knowledge_panel.isVisible():
            self._refresh_knowledge_panel()

        self._ingest_thread.quit()

    @Slot()
    def _on_ingest_thread_finished(self) -> None:
        self._ingest_thread = None
        self._ingest_worker = None
        self._knowledge_panel.set_ingest_running(False)




    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            # event is already a QKeyEvent when type is KeyPress — cast directly
            # Ctrl+Shift+D toggles the developer panel (dev mode only)
            if (event.key() == Qt.Key.Key_D
                    and event.modifiers() == (Qt.KeyboardModifier.ControlModifier
                                              | Qt.KeyboardModifier.ShiftModifier)):
                self._toggle_dev_panel()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    if obj is self._input_box:
                        self._send_companion()
                        return True
                    if obj is self._story_input:
                        self._send_story()
                        return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        if self._CONFIG_PATH.exists():
            try:
                s = json.loads(self._CONFIG_PATH.read_text())
                s = load_secrets(s)
                self._settings_panel.apply_settings(s)
                self._core.apply_settings(s)
                # Apply TTS/STT without going through the signal
                self._tts_enabled = s.get("tts_enabled", True)
                self._tts.update_elevenlabs_key(s.get("elevenlabs_key", ""))
                self._tts_espeak.voice = s.get("tts_voice", "en-us") or "en-us"
                self._tts_espeak.speed = int(s.get("tts_speed", 150))
                self._tts_espeak.pitch = int(s.get("tts_pitch", 50))
                self._stt_enabled = s.get("stt_enabled", True)
                self._mic_btn.setVisible(self._stt_enabled)
                self._show_timestamps = s.get("show_timestamps", False)
                # Restore window geometry
                geom_b64 = s.get("window_geometry", "")
                if geom_b64:
                    self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode()))
            except (json.JSONDecodeError, OSError):
                pass

        # Restore most recent session (if any)
        sessions = self._core.list_sessions()
        if sessions:
            most_recent = sessions[0]
            self._active_session = most_recent
            self._core.load_session(most_recent)
            if most_recent.chat_html:
                self._chat_view.setHtml(most_recent.chat_html)
                self._chat_view.moveCursor(QTextCursor.MoveOperation.End)
                self._chat_view.ensureCursorVisible()

    def _save_settings(self, s: dict) -> None:
        try:
            self._CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            persisted = scrub_and_store_secrets(s)
            temp_path = self._CONFIG_PATH.with_suffix(self._CONFIG_PATH.suffix + ".tmp")
            temp_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")
            temp_path.replace(self._CONFIG_PATH)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status(self) -> None:
        label = getattr(self._core, "provider_label", "No provider")
        info = getattr(self._core.provider, "availability_info", {})
        if isinstance(info, dict) and not bool(info.get("available", True)):
            reason = str(info.get("reason", "Unavailable")).strip()
            self._provider_label.setText(f"Backend: {label} (unavailable: {reason})")
            self._provider_label.setToolTip(str(info.get("retry_hint", "")).strip())
            return

        self._provider_label.setText(f"Backend: {label}")
        self._provider_label.setToolTip("")

    def _poll_backend_status(self) -> None:
        """Query Ollama /api/ps in a daemon thread; update status bar with GPU/CPU info."""
        from auranexus.engine.ollama_provider import OllamaProvider
        if not isinstance(self._core.provider, OllamaProvider):
            return
        base = self._core.provider.base_url

        def _fetch():
            import urllib.request
            import json as _json
            try:
                with urllib.request.urlopen(f"{base}/api/ps", timeout=2) as r:
                    data = _json.loads(r.read())
                models = data.get("models", [])
                if models:
                    m = models[0]
                    # Ollama ≥0.18 uses 'processor' field: '100% GPU', '100% CPU', etc.
                    processor = m.get("processor", "")
                    name = m.get("name", "").split(":")[0]
                    if processor:
                        tag = "🟢 GPU" if "gpu" in processor.lower() else "🟡 CPU"
                        text = f"Backend: {getattr(self._core, 'provider_label', name)}  {tag}"
                        QTimer.singleShot(0, lambda t=text: self._provider_label.setText(t))
            except Exception:
                QTimer.singleShot(0, self._update_status)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _toggle_session_panel(self) -> None:
        visible = not self._session_panel.isVisible()
        if visible:
            self._settings_panel.setVisible(False)
            self._settings_btn.setChecked(False)
            self._log_panel.setVisible(False)
            self._log_btn.setChecked(False)
            self._memory_panel.setVisible(False)
            self._memory_btn.setChecked(False)
            self._lorebook_panel.setVisible(False)
            self._lorebook_btn.setChecked(False)
            self._world_state_panel.setVisible(False)
            self._world_state_btn.setChecked(False)
            self._knowledge_panel.setVisible(False)
            self._knowledge_btn.setChecked(False)
            self._canvas_panel.setVisible(False)
            self._canvas_btn.setChecked(False)
        self._session_panel.setVisible(visible)
        self._chats_btn.setChecked(visible)
        if visible:
            self._refresh_session_list()

    def _refresh_session_list(self) -> None:
        self._session_list.clear()
        sessions = self._core.list_sessions()
        for s in sessions:
            item = QListWidgetItem(s.name)
            item.setData(Qt.ItemDataRole.UserRole, s.session_id)
            self._session_list.addItem(item)
        # Highlight active session
        for i in range(self._session_list.count()):
            if self._session_list.item(i).data(Qt.ItemDataRole.UserRole) == self._active_session.session_id:
                self._session_list.setCurrentRow(i)
                break
        # Re-apply any active filter text
        self._filter_sessions(self._session_filter.text())

    def _filter_sessions(self, text: str) -> None:
        """Show only session list items whose names contain *text* (case-insensitive)."""
        query = text.lower().strip()
        for i in range(self._session_list.count()):
            item = self._session_list.item(i)
            item.setHidden(bool(query and query not in item.text().lower()))

    def _persist_active_session(self) -> None:
        """Snapshot runtime state + chat HTML into the active session and save."""
        self._active_session.recent_turns = list(self._core._recent_turns)
        self._active_session.turn_timestamps = list(self._core._turn_timestamps)
        self._active_session.chat_html = self._chat_view.toHtml()
        self._core.save_session(self._active_session)

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid == self._active_session.session_id:
            return
        if self._streaming:
            QMessageBox.information(self, "Streaming", "Please wait for the current response to finish.")
            return
        # Save current session first
        self._persist_active_session()
        # Find and load the clicked session
        for s in self._core.list_sessions():
            if s.session_id == sid:
                self._active_session = s
                self._core.load_session(s)
                # Restore chat view
                if s.chat_html:
                    self._chat_view.setHtml(s.chat_html)
                    self._chat_view.moveCursor(QTextCursor.MoveOperation.End)
                    self._chat_view.ensureCursorVisible()
                else:
                    self._chat_view.clear()
                break
        self._refresh_session_list()

    def _new_session(self) -> None:
        if self._streaming:
            QMessageBox.information(self, "Streaming", "Please wait for the current response to finish.")
            return
        name, ok = QInputDialog.getText(
            self, "New Chat", "Session name (leave blank for auto):"
        )
        if not ok:
            return
        # Save current session
        self._persist_active_session()
        # Create and activate new session
        self._active_session = self._core.new_session(name.strip())
        self._chat_view.clear()
        self._refresh_session_list()

    def _delete_session(self) -> None:
        item = self._session_list.currentItem()
        if item is None:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid == self._active_session.session_id:
            QMessageBox.information(self, "Active session", "Cannot delete the currently active session.")
            return
        if QMessageBox.question(
            self, "Delete session",
            f'Delete "{item.text()}"? This cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._core.delete_session(sid)
            self._refresh_session_list()

    def _save_session_to_rag(self) -> None:
        """Ingest the current session's turns into the document knowledge base."""
        self._persist_active_session()
        count = self._core.ingest_session_into_rag(self._active_session)
        if count:
            self._save_rag_btn.setText("✓")
            QTimer.singleShot(2000, lambda: self._save_rag_btn.setText("⬆"))
        else:
            QMessageBox.information(
                self, "Nothing to save",
                "No conversation turns to ingest yet, or the knowledge base is unavailable."
            )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Gracefully stop background workers before UI teardown."""
        self._is_closing = True

        # Stop active stream worker first.
        if self._worker is not None:
            try:
                self._worker.request_stop()
            except Exception:
                pass
            # Prevent queued late packets from touching a closing UI.
            try:
                self._worker.token_received.disconnect(self._accumulate_token)
            except Exception:
                pass
            try:
                self._worker.stream_done.disconnect(self._on_stream_done)
            except Exception:
                pass
            try:
                self._worker.error_occurred.disconnect(self._on_stream_error)
            except Exception:
                pass
        self._cleanup_thread()

        # Stop STT thread if running.
        if self._stt_thread is not None and self._stt_thread.isRunning():
            self._stt_thread.quit()
            if not self._stt_thread.wait(2000):
                self._stt_thread.terminate()
                self._stt_thread.wait(1000)

        # Stop ingestion thread if running.
        if self._ingest_thread is not None and self._ingest_thread.isRunning():
            self._ingest_thread.quit()
            if not self._ingest_thread.wait(2000):
                self._ingest_thread.terminate()
                self._ingest_thread.wait(1000)

        # Stop active TTS worker thread.
        self._stop_tts()
        if self._tts_thread is not None and self._tts_thread.is_alive():
            self._tts_thread.join(timeout=1.0)

        self._persist_active_session()
        self._save_window_geometry()
        super().closeEvent(event)

    def _save_window_geometry(self) -> None:
        try:
            geom = self.saveGeometry().toBase64().data().decode()
            path = self._CONFIG_PATH
            if path.exists():
                s = load_secrets(json.loads(path.read_text()))
            else:
                s = {}
            s["window_geometry"] = geom
            persisted = scrub_and_store_secrets(s)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")
            temp_path.replace(path)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Dark theme
    # ------------------------------------------------------------------

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-family: "Noto Sans", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QScrollBar:vertical {
                background: #181825;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 4px;
                min-height: 20px;
            }
            QStatusBar {
                background: #181825;
                color: #6c7086;
                font-size: 11px;
            }
            #Sidebar {
                background-color: #161622;
            }
            #SettingsPanel {
                background-color: #1a1a2e;
                border-left: 1px solid #313244;
            }
            """
        )
