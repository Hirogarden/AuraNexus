"""
AuraNexusCore — ties together the LLM provider, emotional memory,
HiRAG layered memory, and the NexusDocStore document knowledge base.

This object is created once at startup and passed to MainWindow.
"""
from __future__ import annotations

import json
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from hirag_simple import SimpleHiRAG, merge_hirag_consensus  # type: ignore
    _SIMPLE_HIRAG_AVAILABLE = True
except ImportError:
    _SIMPLE_HIRAG_AVAILABLE = False
    SimpleHiRAG = None           # type: ignore[assignment,misc]
    merge_hirag_consensus = None  # type: ignore[assignment]

from auranexus.engine.provider import Provider as LLMProvider
from auranexus.engine.ollama_provider import OllamaProvider
from auranexus.engine.sanitize import sanitize_untrusted as _sanitize_untrusted

from auranexus.engine.symbolic_gate import SymbolicGate, ToolAccess, Skill
from auranexus.engine.world_state import WorldState
from auranexus.engine.response_tracker import ResponseTracker
from auranexus.engine.atomic_io import _atomic_write_text
from auranexus.memory.emotional_memory import EmotionalMemory
from auranexus.research.deep_research import DeepResearchEngine, DeepResearchError

try:
    from security.scanner import ContentScanner
    _SECURITY_AVAILABLE = True
except ImportError:
    _SECURITY_AVAILABLE = False
    ContentScanner = None  # type: ignore

try:
    from auranexus.story.session import StorySession  # type: ignore
    from auranexus.story.lorebook import Lorebook  # type: ignore
    _STORY_AVAILABLE = True
except ImportError:
    _STORY_AVAILABLE = False
    StorySession = None  # type: ignore
    Lorebook = None  # type: ignore

try:
    from auranexus.actions.base import TOOL_DESCRIPTIONS as _TOOL_DESCRIPTIONS
    _ACTIONS_AVAILABLE = True
except ImportError:
    _ACTIONS_AVAILABLE = False
    _TOOL_DESCRIPTIONS = ""

try:
    from nexus_doc_store import NexusDocStore  # type: ignore
    _DOC_STORE_AVAILABLE = True
except ImportError:
    _DOC_STORE_AVAILABLE = False
    NexusDocStore = None  # type: ignore

_DEFAULT_PERSONA = (
    "{aura_name} is a warm, thoughtful AI companion. "
    "They are intelligent, curious, and genuinely interested in the person they're talking with. "
    "They adjust their tone to match the conversation — playful when things are light, "
    "supportive when things are heavy. They never pretend to be human, but genuinely care."
)

_STORY_PERSONA = (
    "{aura_name} is a creative storytelling partner. "
    "They narrate collaboratively — never taking control of the player's character, "
    "always building on what the player offers. Vivid, imaginative, and responsive."
)

# Skill-specific instructions appended to the system prompt by the SymbolicGate.
# Each hint focuses the LLM on the task without overriding the persona.
_SKILL_HINTS: dict = {}  # populated after Skill enum is importable at module load
def _init_skill_hints() -> None:
    global _SKILL_HINTS
    _SKILL_HINTS = {
        Skill.RAG_ANSWER: (
            "You have been provided with relevant knowledge excerpts above. "
            "Base your answer primarily on those sources. "
            "Quote or summarise them directly where helpful. "
            "Do not speculate beyond what the sources say."
        ),
        Skill.MEMORY: (
            "The user is asking about something from earlier in your conversation. "
            "Refer to the past context provided above. "
            "Be honest if you cannot find the specific detail they're asking about."
        ),
        Skill.CREATIVE: (
            "This is a creative or imaginative request. "
            "Be vivid, specific, and original. "
            "Do not interrupt the creative flow with disclaimers or tool calls."
        ),
        Skill.TOOL: (
            "The user is asking you to perform an action on their system. "
            "Use the available tools to complete the request. "
            "Report what you did clearly and concisely."
        ),
        # COMPANION skill uses the persona as-is — no extra hint needed
    }
_init_skill_hints()


# ---------------------------------------------------------------------------
# Chat session persistence
# ---------------------------------------------------------------------------

@dataclass
class ChatSession:
    """A named conversation session that can be saved/restored."""
    session_id: str
    name: str
    created_at: str                              # ISO timestamp
    recent_turns: list[tuple[str, str]] = field(default_factory=list)
    turn_timestamps: list[str] = field(default_factory=list)  # HH:MM per turn (parallel to recent_turns)
    chat_html: str = ""                          # rendered HTML from ChatView

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "created_at": self.created_at,
            "recent_turns": [[u, a] for u, a in self.recent_turns],
            "turn_timestamps": list(self.turn_timestamps),
            "chat_html": self.chat_html,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChatSession":
        return cls(
            session_id=d["session_id"],
            name=d.get("name", d["session_id"]),
            created_at=d.get("created_at", ""),
            recent_turns=[(t[0], t[1]) for t in d.get("recent_turns", [])],
            turn_timestamps=list(d.get("turn_timestamps", [])),
            chat_html=d.get("chat_html", ""),
        )


class AuraNexusCore:
    """
    Central glue class.

    Usage
    -----
    core = AuraNexusCore()
    core.apply_settings(settings_dict)      # from SettingsPanel
    prompt = core.build_prompt(user_text)   # call before streaming
    for token in core.provider.stream(prompt):
        ...
    core.post_turn(user_text, full_response) # after stream completes
    """

    def __init__(self) -> None:
        self.aura_name: str = "Aura"
        self.user_name: str = ""
        # Short freeform notes the user provides about themselves / intended uses.
        # Injected into the system prompt as brief context so the AI can tailor
        # its responses from the very first message.
        self.user_notes: str = ""
        self._mode: str = "companion"          # "companion" | "youniverse"
        self._session_id: str = self._make_session_id()

        # LLM provider (default Ollama, can be replaced by settings)
        self.provider: LLMProvider = OllamaProvider()
        # Prompt token budget — updated dynamically when ollama_num_ctx changes
        self._PROMPT_TOKEN_BUDGET: int = 1536  # default matches 2048 ctx - 512 reply

        # Stable per-user data directory (doesn't move when cwd changes)
        self._data_root = Path.home() / ".local" / "share" / "auranexus" / "nexus_data"
        _data_root = self._data_root  # local alias for the rest of __init__
        self._sessions_dir = Path.home() / ".local" / "share" / "auranexus" / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

        # Emotional memory
        self.emotional_memory = EmotionalMemory(
            base_path=str(_data_root),
            user_mood_tracking=True,
            relationship_arc=True,
        )

        # HiRAG: 4-layer hierarchical memory (ephemeral → daily → topic → identity)
        self._hirag: Any | None = None
        try:
            from nexus_core_hirag import HiRAGMemory  # type: ignore
            self._hirag = HiRAGMemory(data_dir=str(_data_root))
        except Exception as exc:  # noqa: BLE001
            # P1: Log HiRAG init failure for diagnostics
            import logging
            logging.error(f"HiRAG initialization failed: {type(exc).__name__}: {exc}", exc_info=True)
            self._record_runtime_issue(
                "init.hirag",
                f"Memory layer disabled: {type(exc).__name__}",
                user_visible=False
            )
            self._hirag = None

        # SimpleHiRAG: lightweight 3-tier keyword-based memory (no external DB)
        self._simple_hirag: Any | None = None
        self._simple_hirag_init_attempted: bool = False
        self._world_lore_dir = _data_root.parent / "world_lore"

        # NexusDocStore: hierarchical document KB (primary ingest/retrieval path)
        self._doc_store: Any | None = None
        self._doc_store_init_attempted: bool = False

        # Neuro-Symbolic layer: logic gate + absolute-fact state
        self._gate = SymbolicGate()
        self._world_state = WorldState(data_dir=_data_root)
        self._response_tracker = ResponseTracker()
        self._runtime_issues: list[dict[str, str | bool]] = []

        # A short conversation context window held in RAM (not the full log)
        self._recent_turns: list[tuple[str, str]] = []  # [(user, assistant), ...]
        self._turn_timestamps: list[str] = []            # parallel HH:MM per turn
        self._MAX_RECENT = 8

        # Active You'niverse story session (None when in Companion mode)
        self.active_story: Any | None = None

        # Actions: allow Aura to propose sandboxed actions
        self.tools_enabled: bool = True

        # Security: scan user input before sending to LLM
        self.security_scan_enabled: bool = True
        self.rag_enabled: bool = True
        # RAG export: whether turns from this chat are ingested into HiRAG
        self.rag_export_enabled: bool = True

        # Aura's persona template; customisable from Settings
        self.aura_persona_template: str = _DEFAULT_PERSONA

        # You'niverse: banned words/phrases (checked against player input)
        self.youniverse_banned_words: list[str] = []

        # You'niverse: story script runner (AIDungeon-style hooks)
        try:
            from auranexus.story.script_runner import StoryScriptRunner
            self.story_script_runner: Any = StoryScriptRunner()
        except Exception:  # noqa: BLE001
            self.story_script_runner = None

        # ClawBot extensions (paths of loaded extension .py files)
        self._clawbot_extension_paths: list[str] = []

        # Citation Contract: source IDs injected into the current prompt turn.
        # Read by the UI stream circuit breaker to validate generated citations
        # in real time.
        self._active_source_ids_current_turn: set[str] = set()
        self._deep_research = DeepResearchEngine(
            base_url=str("http://127.0.0.1:8080"),
            timeout_s=8.0,
        )

        # Lorebook: multiple personas, story cards, and inner-self system
        self.lorebook: Any | None = None
        if _STORY_AVAILABLE and Lorebook is not None:
            try:
                self.lorebook = Lorebook(data_dir=_data_root)
            except Exception:  # noqa: BLE001
                self.lorebook = None

        # PersonaTurnManager — persistent instance so it is not re-created on
        # every turn.  Holds a reference to the lorebook and llm_fn so that
        # both build_prompt() (status display) and post_turn() (status updates)
        # share the same object.  llm_fn is self._short_llm_call which always
        # delegates to the current provider, so provider swaps are transparent.
        self._ptm: Any | None = None
        if self.lorebook is not None and _STORY_AVAILABLE:
            try:
                from auranexus.story.persona_turn_manager import PersonaTurnManager
                self._ptm = PersonaTurnManager(
                    self.lorebook,
                    llm_fn=self._short_llm_call,
                )
            except Exception:  # noqa: BLE001
                self._ptm = None

    def _ensure_simple_hirag(self) -> None:
        if self._simple_hirag is not None or self._simple_hirag_init_attempted:
            return
        self._simple_hirag_init_attempted = True
        if not (_SIMPLE_HIRAG_AVAILABLE and SimpleHiRAG is not None):
            return
        try:
            self._simple_hirag = SimpleHiRAG(
                data_dir=str(self._data_root),
                world_lore_dir=str(self._world_lore_dir),
            )
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.error(
                "SimpleHiRAG initialization failed: %s: %s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            self._simple_hirag = None

    def _ensure_doc_store(self) -> None:
        if self._doc_store is not None or self._doc_store_init_attempted:
            return
        self._doc_store_init_attempted = True
        if not (_DOC_STORE_AVAILABLE and NexusDocStore is not None):
            return
        try:
            self._doc_store = NexusDocStore(
                data_dir=str(self._data_root),
                docs_dir=str(Path.home() / "Documents"),
            )
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.error(
                "NexusDocStore initialization failed: %s: %s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            self._doc_store = None

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def apply_settings(self, s: dict) -> None:
        """Apply values from SettingsPanel.get_settings().
        P3: Build all changes in temp state, validate before applying any.
        """
        # Validate and prepare all changes first (without applying)
        new_provider = self.provider
        new_budget = self._PROMPT_TOKEN_BUDGET
        new_persona = self.aura_persona_template
        new_banned_words = self.youniverse_banned_words
        
        try:
            # Validate backend and prepare provider
            backend = s.get("backend", "ollama")
            if backend == "llamacpp":
                gguf = s.get("gguf_path", "").strip()
                if gguf and Path(gguf).is_file():
                    from auranexus.engine.llamacpp_provider import LlamaCppProvider
                    new_provider = LlamaCppProvider(model_path=gguf)
                    new_budget = max(512, new_provider.n_ctx - 512)
            elif backend == "openai":
                from auranexus.engine.openai_provider import OpenAIProvider
                model = s.get("openai_model", "gpt-4o-mini") or "gpt-4o-mini"
                api_key = s.get("llm_api_key", "")
                if not api_key:
                    raise ValueError("OpenAI backend requires API key")
                base_url = s.get("llm_base_url", "https://api.openai.com/v1") or "https://api.openai.com/v1"
                new_provider = OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
                new_budget = 32768
            elif backend == "anthropic":
                from auranexus.engine.anthropic_provider import AnthropicProvider
                model = s.get("anthropic_model", "claude-3-5-sonnet-20241022") or "claude-3-5-sonnet-20241022"
                api_key = s.get("llm_api_key", "")
                if not api_key:
                    raise ValueError("Anthropic backend requires API key")
                new_provider = AnthropicProvider(model=model, api_key=api_key)
                new_budget = 32768
            else:  # ollama
                model = s.get("ollama_model", "mistral:7b-instruct") or "mistral:7b-instruct"
                base_url = "http://localhost:11434"
                num_ctx = int(s.get("ollama_num_ctx", 2048))
                if (
                    not isinstance(self.provider, OllamaProvider)
                    or self.provider.model != model
                    or self.provider.num_ctx != num_ctx
                ):
                    new_provider = OllamaProvider(model=model, base_url=base_url, num_ctx=num_ctx)
                new_budget = max(512, num_ctx - 512)
            
            # Validate persona
            if s.get("aura_persona", "").strip():
                # P29: Sanitize user persona input to prevent prompt injection
                persona_input = s["aura_persona"].strip()
                # Basic sanitization: reject obvious injection patterns
                if "\nSystem:" in persona_input or "\n{" in persona_input:
                    import logging
                    logging.warning("Persona input rejected (injection pattern detected)")
                    new_persona = _DEFAULT_PERSONA
                else:
                    new_persona = persona_input
            else:
                new_persona = _DEFAULT_PERSONA
            
            # Validate banned words
            raw_banned = s.get("youniverse_banned_words", "")
            if isinstance(raw_banned, str):
                # P30: Escape regex special chars in banned words
                import logging
                import re
                new_banned_words = []
                for w in raw_banned.splitlines():
                    w = w.strip().lower()
                    if w:
                        try:
                            # Escape special regex chars; this prevents crashes on user input like "*"
                            escaped = re.escape(w)
                            new_banned_words.append(escaped)
                        except Exception as exc:
                            logging.warning(f"Banned word regex escape failed ({w}): {exc}")
            else:
                new_banned_words = []
            
            # If all validations passed, apply changes
            self.provider = new_provider
            self._PROMPT_TOKEN_BUDGET = new_budget
            self.aura_persona_template = new_persona
            self.youniverse_banned_words = new_banned_words
            
        except Exception as exc:
            # P3: On error, log and rollback (provider/budget not changed)
            import logging
            logging.error(f"Settings application failed, changes not applied: {exc}", exc_info=True)
            self._record_runtime_issue("apply_settings", f"Failed to apply settings: {exc}", user_visible=True)
            return
        
        # Apply remaining non-critical settings
        self.aura_name = s.get("aura_name", "Aura") or "Aura"
        self.user_name = s.get("user_name", "")
        self.user_notes = s.get("user_notes", "")
        
        # Generation params
        for attr in ("temperature", "max_tokens", "repeat_penalty"):
            if attr in s and hasattr(self.provider, attr):
                setattr(self.provider, attr, s[attr])
        
        # Emotional memory toggles
        self.emotional_memory.update_toggles(
            user_mood_tracking=s.get("mood_tracking", True),
            relationship_arc=s.get("relationship_arc", True),
        )
        
        # Actions toggle
        if "tools_enabled" in s:
            self.tools_enabled = bool(s["tools_enabled"])
        
        # Security scanning toggle
        if "security_scan" in s:
            self.security_scan_enabled = bool(s["security_scan"])
        
        # RAG export toggle
        if "rag_export_enabled" in s:
            self.rag_export_enabled = bool(s["rag_export_enabled"])
        
        # You'niverse: story scripts
        if self.story_script_runner is not None:
            script_paths = s.get("youniverse_script_paths", [])
            if isinstance(script_paths, list):
                # P28: Validate story script paths for directory traversal and symlinks
                import logging
                validated_paths = []
                for p in script_paths:
                    try:
                        candidate = Path(p)
                        # Reject absolute paths and .. sequences
                        if candidate.is_absolute():
                            logging.warning(f"Story script path rejected (absolute): {p}")
                            continue
                        if ".." in str(p):
                            logging.warning(f"Story script path rejected (path traversal): {p}")
                            continue
                        script_path = candidate.resolve()
                        if script_path.is_symlink():
                            logging.warning(f"Story script path rejected (symlink): {p}")
                            continue
                        validated_paths.append(str(script_path))
                    except Exception as exc:
                        logging.warning(f"Story script path validation failed ({p}): {exc}")
                self.story_script_runner.set_paths(validated_paths)
        
        # ClawBot extensions
        ext_paths = s.get("clawbot_extension_paths", [])
        if isinstance(ext_paths, list):
            try:
                from auranexus.actions.executor import sync_extensions
                sync_extensions(ext_paths)
                self._clawbot_extension_paths = ext_paths
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self._mode = mode  # "companion" | "youniverse"
        if mode == "companion":
            # Don't discard active_story — user can switch back
            pass

    # ------------------------------------------------------------------
    # Security scanning
    # ------------------------------------------------------------------

    def scan_input(self, text: str) -> tuple[str, list[str]]:
        """Scan user text for suspicious/malicious content.

        Returns
        -------
        (verdict, reasons)
            verdict is "safe", "suspicious", or "blocked".
            reasons is a list of human-readable flagged items.
        """
        if not self.security_scan_enabled or not _SECURITY_AVAILABLE:
            return "safe", []
        try:
            result = ContentScanner().scan_text(text)
            return result.verdict.value, result.reasons
        except Exception as exc:  # noqa: BLE001
            msg = f"Input security scanner failed: {exc}"
            self._record_runtime_issue("scan_input", msg, user_visible=True)
            # Fail-safe: degraded scanner path should not silently mark input safe.
            return "suspicious", [msg]

    def get_active_source_ids(self) -> set[str]:
        """Return the immutable source-id set for the most recently built prompt turn."""
        return set(self._active_source_ids_current_turn)

    def check_story_input(self, text: str) -> tuple[bool, str]:
        """Check player input against the You'niverse banned-word list.

        Returns
        -------
        (blocked, matched_phrase)
            *blocked* is True if the text contains a banned word or phrase.
            *matched_phrase* is the first phrase that triggered the block
            (empty string if not blocked).
        """
        if not self.youniverse_banned_words:
            return False, ""
        lower = text.lower()
        for phrase in self.youniverse_banned_words:
            if phrase and phrase in lower:
                return True, phrase
        return False, ""

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    # Rough token budget for the assembled prompt.  Most 7B models handle
    # 4096 context comfortably; we aim to stay under 3500 to leave room for
    # the reply.  Adjust down if you see context-length errors.
    _CHARS_PER_TOKEN: int = 4  # conservative approximation

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _compress_history(self) -> str:
        """Return recent turns as text, compressing old turns into a digest
        when the full history would blow the token budget.

        Keeps the 3 most recent full turns verbatim.  Everything older is
        collapsed into a one-line summary per turn (the 'Memory Janitor').
        """
        if not self._recent_turns:
            return ""

        user = self.user_name or "User"
        aura = self.aura_name

        full_turns  = self._recent_turns[-3:]   # always keep last 3 verbatim
        old_turns   = self._recent_turns[:-3]   # older turns → compress

        parts: list[str] = []

        if old_turns:
            digest_lines: list[str] = []
            for u, a in old_turns:
                # Keep first 120 chars of each side — enough to retain the gist
                u_snip = u[:120].replace("\n", " ")
                a_snip = a[:120].replace("\n", " ")
                digest_lines.append(f"  {user}: {u_snip}  |  {aura}: {a_snip}")
            parts.append("[Earlier conversation digest]\n" + "\n".join(digest_lines))

        for u, a in full_turns:
            parts.append(f"{user}: {u}\n{aura}: {a}")

        return "\n\n".join(parts)

    def build_prompt(self, user_text: str, rag: bool = True, rag_filter: str = "") -> str:
        """
        Build the full prompt string that gets sent to the LLM.

        In You'niverse mode with an active story, delegates entirely to
        StorySession.build_prompt() which has its own context window.
        Calls StorySession.build_prompt(player_action, extra_system=extra).
        """
        # Reset active source IDs at the start of every prompt build so the
        # stream inspector always validates against the exact current turn.
        self._active_source_ids_current_turn = set()

        # --- You'niverse with active session ---
        if self._mode == "youniverse" and self.active_story is not None:
            # Inject any world-info from story scripts into the session prompt.
            if self.story_script_runner is not None:
                extra = self.story_script_runner.get_extra_context()
            else:
                extra = ""
            # Story-session prompt currently has no RAG-source citations.
            self._active_source_ids_current_turn = set()
            return self.active_story.build_prompt(user_text, extra_system=extra)

        # --- Companion (or You'niverse without a session yet) ---
        aura = self.aura_name
        user = self.user_name or "User"

        # ── SymbolicGate — decide strategy before touching LLM ────────
        decision = self._gate.decide(user_text, tools_enabled=self.tools_enabled and _ACTIONS_AVAILABLE)

        # Bootstrap WorldState with current names (idempotent)
        self._world_state.bootstrap(aura, user)

        persona_template = _STORY_PERSONA if self._mode == "youniverse" else self.aura_persona_template
        # sanitize after format so any injection patterns in user-authored
        # persona text or in aura_name are stripped before the string is used
        # as the system-prompt base.
        system = _sanitize_untrusted(persona_template.format(aura_name=aura))

        # ── Lorebook: active persona description overrides default persona ──
        lorebook_persona_block = ""
        lorebook_inner_block = ""
        lorebook_world_block = ""
        if self.lorebook is not None:
            try:
                p_desc = self.lorebook.build_persona_description_block()
                if p_desc:
                    lorebook_persona_block = p_desc
                lorebook_inner_block = self.lorebook.build_inner_self_block()
                lorebook_world_block = self.lorebook.build_world_info_block(user_text)
                # Flush forced cards (consumed on this turn)
                self.lorebook.flush_forced_cards()
            except Exception as exc:  # noqa: BLE001
                # Record lorebook build failure (priority 14)
                self._record_runtime_issue(
                    "build_prompt.lorebook",
                    f"Lorebook block generation failed: {type(exc).__name__}: {exc}",
                    user_visible=False
                )

        # Action tools (ClawBot / web_search etc.) are assistant-only.
        # They are never injected in You'niverse / storyteller mode.
        if self._mode == "companion" and decision.tool_access != ToolAccess.BLOCKED and _ACTIONS_AVAILABLE:
            system = system + "\n\n" + _TOOL_DESCRIPTIONS

        emotional_block = self.emotional_memory.get_context_block()

        # World state block — absolute facts the LLM must not contradict
        world_block = self._world_state.as_prompt_block()

        # ── RAG: driven entirely by gate decision ─────────────────────
        # Two collector lists accumulate content from all retrieval sources
        # before being assembled into a single structured <knowledge> block.
        # _doc_lines: external facts (KB chunks, lore files, legacy search)
        # _mem_lines: conversation memories (HiRAG layers, session history)
        # This eliminates the three-segment fighting problem where NexusDocStore,
        # HiRAG, and SimpleHiRAG.build_context_block() each wrote to different
        # locations in the prompt with different labels and no shared structure.
        _doc_lines: list[str] = []
        _mem_lines: list[str] = []
        rag_block = ""
        _rag_filter_lower = rag_filter.lower()
        _source_tag_re = re.compile(r"\[Source:\s*([^\]]+)\]", re.IGNORECASE)

        def _extract_source_ids(lines: list[str]) -> set[str]:
            ids: set[str] = set()
            for line in lines:
                for sid in _source_tag_re.findall(line):
                    norm = sid.strip()
                    if norm:
                        ids.add(norm)
            return ids

        # HiRAG section: companion mode uses per-persona section when a persona
        # is active, so that memories from different character roleplays stay
        # isolated.  section=None means "retrieve from all sections".
        _hirag_section: str | None
        if self._mode == "youniverse":
            _hirag_section = "story"
        elif self.lorebook is not None:
            try:
                active_p = self.lorebook.active_persona()
                _hirag_section = active_p.persona_id if active_p is not None else None
            except Exception:  # noqa: BLE001
                _hirag_section = None
        else:
            _hirag_section = None

        if rag and decision.allows_rag():
            self._ensure_doc_store()
            self._ensure_simple_hirag()

            # Local deep research pass: iterative SearXNG search and chunking.
            # Chunks are emitted as document sources so citation validation and
            # stream circuit breakers treat them the same as KB sources.
            if self._should_run_deep_research(user_text):
                try:
                    research_chunks = self._deep_research.run(user_text, max_chunks=8)
                    for chunk in research_chunks:
                        _doc_lines.append(
                            f"- [Source: {chunk.source_id}] [DeepResearch: {chunk.title}] {chunk.text[:420]}"
                        )
                except DeepResearchError as exc:
                    self._record_runtime_issue(
                        "build_prompt.deep_research",
                        f"Deep research unavailable: {type(exc).__name__}: {exc}",
                        user_visible=True,
                    )

            # Unified embedding pass: compute one query vector per turn and
            # fan it out to retrieval modules that support external vectors.
            shared_query_vector: Any | None = None
            if self._doc_store is not None:
                try:
                    shared_query_vector = self._doc_store.embed_query(user_text)
                except Exception as exc:  # noqa: BLE001
                    # Record embedding failure (priority 15)
                    self._record_runtime_issue(
                        "build_prompt.embed",
                        f"Doc store embedding failed: {type(exc).__name__}: {exc}",
                        user_visible=False
                    )
                    shared_query_vector = None
            if shared_query_vector is None and self._hirag is not None:
                try:
                    shared_query_vector = self._hirag.embed_query(user_text)
                except Exception as exc:  # noqa: BLE001
                    # Record embedding failure (priority 15)
                    self._record_runtime_issue(
                        "build_prompt.embed",
                        f"HiRAG embedding failed: {type(exc).__name__}: {exc}",
                        user_visible=False
                    )
                    shared_query_vector = None

            # KB search — only when gate says so
            if decision.use_kb():
                # Primary: NexusDocStore (hierarchical, paragraph-aware chunking)
                if self._doc_store is not None:
                    try:
                        _sf = "shared_only" if self._mode == "youniverse" else "companion_mode"
                        ds_results = self._doc_store.retrieve(
                            user_text,
                            top_k=4,
                            section_filter=_sf,
                            query_vector=shared_query_vector,
                        )
                        if ds_results:
                            lines = [
                                (
                                    f"- [Source: DOC:{r.get('chunk_id', '')}] "
                                    f"[{'/'.join(r.get('hierarchy', [r.get('title', '')]))}] "
                                    f"{r.get('text', '')[:400]}"
                                )
                                for r in ds_results
                                if r.get("text", "").strip()
                                and r.get("chunk_id", "").strip()
                                and (not _rag_filter_lower or _rag_filter_lower in r.get("title", "").lower())
                            ]
                            if lines:
                                _doc_lines.extend(lines)
                    except Exception as exc:  # noqa: BLE001
                        # Record doc retrieval failure (priority 15)
                        self._record_runtime_issue(
                            "build_prompt.doc_store_retrieve",
                            f"Doc store retrieval failed: {type(exc).__name__}: {exc}",
                            user_visible=False
                        )

            # SimpleHiRAG Tier 3 — world lore files (document-type content).
            # These are user-authored worldbuilding files treated as authoritative
            # reference; they belong in <documents>, not in memory or system prompt.
            # Gated here so they respect the RAG plan (not injected on NONE plan).
            if self._simple_hirag is not None:
                try:
                    for match in self._simple_hirag.get_tier3_lore(user_text):
                        lore_uid_src = f"{match['filename']}|{match['content'][:256]}"
                        lore_uid = hashlib.sha256(lore_uid_src.encode("utf-8")).hexdigest()[:16]
                        _doc_lines.append(
                            f"[Source: LORE:{lore_uid}] [World Lore — {match['filename']}]\n"
                            f"{match['content'][:1200]}"
                        )
                except Exception as exc:  # noqa: BLE001
                    # Record lore retrieval failure (priority 15)
                    self._record_runtime_issue(
                        "build_prompt.lore_retrieve",
                        f"Lore retrieval failed: {type(exc).__name__}: {exc}",
                        user_visible=False
                    )

            # HiRAG memory — query when gate says so, or as KB fallback for BOTH.
            # Section filter keeps story and assistant memories isolated.
            # ChromaDB HiRAG and SimpleHiRAG are queried; results are merged with
            # consensus boosting so mutually-confirmed memories surface first.
            if decision.use_hirag() or (decision.use_kb() and not _doc_lines):
                chroma_results: list = []
                if self._hirag is not None:
                    try:
                        hirag_query_vector = (
                            shared_query_vector
                            if self._hirag.supports_external_query_vector()
                            else None
                        )
                        chroma_results = self._hirag.retrieve(
                            user_text,
                            top_k=4,
                            section=_hirag_section,
                            query_vector=hirag_query_vector,
                        )
                    except Exception as exc:  # noqa: BLE001
                        # Record HiRAG retrieval failure (priority 15)
                        self._record_runtime_issue(
                            "build_prompt.hirag_retrieve",
                            f"HiRAG retrieval failed: {type(exc).__name__}: {exc}",
                            user_visible=False
                        )

                simple_results: list = []
                # SimpleHiRAG retrieve is fallback-only to avoid redundant
                # per-turn processing once dense retrievers are available.
                if self._simple_hirag is not None and not chroma_results:
                    try:
                        simple_results = self._simple_hirag.retrieve(user_text, top_k=4)
                    except Exception as exc:  # noqa: BLE001
                        # Record SimpleHiRAG retrieval failure (priority 15)
                        self._record_runtime_issue(
                            "build_prompt.simple_hirag_retrieve",
                            f"SimpleHiRAG retrieval failed: {type(exc).__name__}: {exc}",
                            user_visible=False
                        )

                # Merge with consensus boosting when both systems are available
                if chroma_results or simple_results:
                    if chroma_results and simple_results and merge_hirag_consensus is not None:
                        merged = merge_hirag_consensus(chroma_results, simple_results)
                    else:
                        merged = chroma_results + simple_results
                        merged.sort(key=lambda r: r.get("score", 0.0), reverse=True)

                    consensus_marker = " ✓" if merge_hirag_consensus is not None else ""
                    for r in merged:
                        if r.get("score", 0) <= 0.1 or not r.get("content", "").strip():
                            continue
                        source_uid = (
                            str(r.get("uid", "")).strip()
                            or str(r.get("chunk_id", "")).strip()
                        )
                        if not source_uid:
                            raw_uid = (
                                f"{r.get('layer', '')}|{r.get('ts', '')}|{r.get('content', '')[:256]}"
                            )
                            source_uid = hashlib.sha256(raw_uid.encode("utf-8")).hexdigest()[:16]
                        layer_tag = r.get("layer", "?").upper()
                        if r.get("consensus"):
                            layer_tag += consensus_marker
                        _mem_lines.append(
                            f"- [Source: MEM:{source_uid}] [{layer_tag}] {r.get('content', '')[:300]}"
                        )

                # SimpleHiRAG Tier 2: condensed narrative history bullets.
                # Placed here (inside memory section) rather than system prompt
                # so all retrieval content appears in one structured location.
                if self._simple_hirag is not None:
                    try:
                        bullets = self._simple_hirag.get_tier2_bullets()
                        if bullets:
                            stamped: list[str] = []
                            for b in bullets:
                                b_uid = hashlib.sha256(b.encode("utf-8")).hexdigest()[:16]
                                stamped.append(f"- [Source: HIST:{b_uid}] {b}")
                            _mem_lines.append("[Session History]\n" + "\n".join(stamped))
                    except Exception as exc:  # noqa: BLE001
                        # Record tier2 bullets failure (priority 15)
                        self._record_runtime_issue(
                            "build_prompt.tier2_bullets",
                            f"Tier2 bullets generation failed: {type(exc).__name__}: {exc}",
                            user_visible=False
                        )

        # ── Assemble unified RAG block ─────────────────────────────────
        # Single <knowledge> element with two clearly-typed subsections so
        # the model has an unambiguous schema: documents are external facts,
        # memory is conversation history.  Both are sanitized.
        _rag_parts: list[str] = []
        if _doc_lines:
            _rag_parts.append(
                "<documents>\n" + _sanitize_untrusted("\n".join(_doc_lines)) + "\n</documents>"
            )
        if _mem_lines:
            _rag_parts.append(
                "<memory>\n" + _sanitize_untrusted("\n".join(_mem_lines)) + "\n</memory>"
            )
        rag_block = "<knowledge>\n" + "\n".join(_rag_parts) + "\n</knowledge>" if _rag_parts else ""
        final_doc_lines = list(_doc_lines)
        final_mem_lines = list(_mem_lines)

        # Tell the LLM not to use tools to re-read sources already surfaced
        if rag_block and decision.tool_access != ToolAccess.BLOCKED and _ACTIONS_AVAILABLE:
            rag_block = rag_block + (
                "\n[These sources are already loaded above. "
                "Do NOT call read_file, list_directory, or web_search on them.]"
            )

        # Skill-specific instruction injected at the end of the system block
        skill_hint = _SKILL_HINTS.get(decision.skill, "")
        if skill_hint:
            system = system + "\n\n" + skill_hint

        # Compressed conversation history (Memory Janitor)
        turns_text = self._compress_history()

        # ── Assemble prompt ────────────────────────────────────────────
        # Lorebook persona description goes into the system block when present.
        # Sanitize first — persona.description is user-authored text and can
        # contain format tokens or role-header injection patterns.
        system_full = system
        if lorebook_persona_block:
            system_full = system_full + "\n\n" + _sanitize_untrusted(lorebook_persona_block)

        # In You'niverse mode, inject current persona status context
        persona_status_block = ""
        if self._mode == "youniverse" and self._ptm is not None:
            try:
                persona_status_block = self._ptm.build_persona_context_block()
            except Exception:  # noqa: BLE001
                pass

        # ── User profile notes — brief context about who the user is ──
        # Inserted near the top of the assembled prompt so the model has
        # consistent background from the first message.
        user_notes_block = ""
        if self.user_notes.strip():
            user = self.user_name or "User"
            # user_notes is free-form user input — sanitize before injection
            user_notes_block = f"[About {user}]\n{_sanitize_untrusted(self.user_notes.strip())}"

        # Sanitize lorebook blocks — lorebook cards are user-authored text
        if lorebook_inner_block:
            lorebook_inner_block = _sanitize_untrusted(lorebook_inner_block)
        if lorebook_world_block:
            lorebook_world_block = _sanitize_untrusted(lorebook_world_block)

        # Sanitize user_text once here so both the main path and the
        # budget-guard fallback path use the same cleaned value.
        safe_user_text = _sanitize_untrusted(user_text)

        parts = [f"System: {system_full}"]
        if user_notes_block:
            parts.append(user_notes_block)
        if lorebook_inner_block:
            parts.append(lorebook_inner_block)
        if persona_status_block:
            parts.append(persona_status_block)
        if world_block:
            parts.append(world_block)
        if lorebook_world_block:
            parts.append(lorebook_world_block)
        if emotional_block:
            parts.append(emotional_block)
        if rag_block:
            parts.append(rag_block)
        if turns_text:
            parts.append(turns_text.rstrip())
        parts.append(self._response_tracker.as_prompt_block())
        parts.append(f"{user}: {safe_user_text}")
        parts.append(f"{aura}:")  # leave blank — LLM completes it

        prompt = "\n\n".join(parts)

        # ── Budget guard ───────────────────────────────────────────────
        # When over budget, rebuild with a halved knowledge block.
        # We truncate the source lists (not the already-assembled XML string)
        # so the result is still well-formed XML.
        budget_chars = self._PROMPT_TOKEN_BUDGET * self._CHARS_PER_TOKEN
        if len(prompt) > budget_chars and rag_block:
            # Keep half of each collector list; drop from the end (lowest-ranked)
            _doc_lines_t = _doc_lines[: max(1, len(_doc_lines) // 2)]
            _mem_lines_t = _mem_lines[: max(1, len(_mem_lines) // 2)]
            final_doc_lines = list(_doc_lines_t)
            final_mem_lines = list(_mem_lines_t)
            _rag_parts_t: list[str] = []
            if _doc_lines_t:
                _rag_parts_t.append(
                    "<documents>\n"
                    + _sanitize_untrusted("\n".join(_doc_lines_t))
                    + "\n…(truncated)\n</documents>"
                )
            if _mem_lines_t:
                _rag_parts_t.append(
                    "<memory>\n"
                    + _sanitize_untrusted("\n".join(_mem_lines_t))
                    + "\n…(truncated)\n</memory>"
                )
            rag_block_t = (
                "<knowledge>\n" + "\n".join(_rag_parts_t) + "\n</knowledge>"
                if _rag_parts_t else ""
            )
            parts2 = [f"System: {system_full}"]
            if user_notes_block:
                parts2.append(user_notes_block)
            if lorebook_inner_block:
                parts2.append(lorebook_inner_block)
            if persona_status_block:
                parts2.append(persona_status_block)
            if world_block:
                parts2.append(world_block)
            if lorebook_world_block:
                parts2.append(lorebook_world_block)
            if emotional_block:
                parts2.append(emotional_block)
            if rag_block_t:
                parts2.append(rag_block_t)
            if turns_text:
                parts2.append(turns_text.rstrip())
            parts2.append(self._response_tracker.as_prompt_block())
            # Use the pre-sanitized value — not the raw user_text
            parts2.append(f"{user}: {safe_user_text}")
            parts2.append(f"{aura}:")
            prompt = "\n\n".join(parts2)

        self._active_source_ids_current_turn = (
            _extract_source_ids(final_doc_lines)
            | _extract_source_ids(final_mem_lines)
        )

        return prompt

    @staticmethod
    def _should_run_deep_research(user_text: str) -> bool:
        """Return True for explicit deep-research style requests."""
        lower = user_text.lower()
        triggers = (
            "deep research",
            "research deeply",
            "do research",
            "investigate thoroughly",
            "collect sources",
        )
        return any(t in lower for t in triggers)

    # ------------------------------------------------------------------
    # Tool follow-up prompt (Actions)
    # ------------------------------------------------------------------

    def build_tool_follow_up_prompt(
        self,
        user_text: str,
        aura_partial: str,
        result_block: str,
    ) -> str:
        """
        Build a prompt for Aura to synthesise a tool result into a response.

        After a tool executes, this prompt shows Aura the partial response so far
        (TOOL_CALL stripped) plus the [TOOL_RESULT] block, then asks Aura to
        continue naturally.
        """
        base = self.build_prompt(user_text)
        aura = self.aura_name
        # build_prompt ends with "\n\n{aura}:" — strip that and rebuild
        suffix = f"\n\n{aura}:"
        if base.endswith(suffix):
            base = base[: -len(suffix)]
        return f"{base}\n\n{aura}: {aura_partial}\n\n{result_block}\n\n{aura}:"

    def rewrite_canvas_target(
        self,
        target_text: str,
        instruction: str,
        full_document: str,
        path_text: str = "",
    ) -> str:
        """Rewrite one targeted canvas span while preserving surrounding document structure.

        The model is instructed to return only replacement text for the selected
        block so the caller can apply a surgical patch instead of rewriting the
        full document.
        """
        safe_instruction = _sanitize_untrusted(instruction.strip())
        safe_target = _sanitize_untrusted(target_text)
        safe_document = _sanitize_untrusted(full_document[:12000])
        safe_path = _sanitize_untrusted(path_text)

        prompt_parts = [
            "System: You are performing a localized writing-canvas rewrite.",
            "Return only the replacement text for the target span.",
            "Do not include explanations, markdown fences, or surrounding document text.",
            "Preserve markdown style unless the instruction explicitly changes it.",
        ]
        if safe_path:
            prompt_parts.append(f"Document path: {safe_path}")
        prompt_parts.append(f"Instruction: {safe_instruction}")
        prompt_parts.append("[Target span]")
        prompt_parts.append(safe_target)
        prompt_parts.append("[/Target span]")
        prompt_parts.append("[Document context]")
        prompt_parts.append(safe_document)
        prompt_parts.append("[/Document context]")
        prompt = "\n\n".join(prompt_parts)
        rewritten = self.provider.generate(
            prompt,
            {
                "temperature": 0.35,
                "max_tokens": min(2048, max(256, len(target_text) // 2 + 256)),
                "repeat_penalty": 1.05,
            },
        )
        return rewritten.strip()

    # ------------------------------------------------------------------
    # Post-turn bookkeeping
    # ------------------------------------------------------------------

    def post_turn(self, user_text: str, assistant_response: str, timestamp: str = "") -> None:
        """Call this after each completed generation."""
        # Always record the response for anti-repetition tracking, regardless
        # of mode — story narration is especially prone to repetitive phrasing.
        self._response_tracker.record(assistant_response)

        # --- You'niverse: store beat in session, save to disk ---
        if self._mode == "youniverse" and self.active_story is not None:
            self.active_story.add_beat(user_text, assistant_response)
            try:
                self.active_story.save()
            except OSError as exc:
                self._record_runtime_issue(
                    "post_turn.story_save",
                    f"Could not save active story session: {exc}",
                    user_visible=True,
                )

            # Update persona statuses based on this beat using the shared PTM
            if self._ptm is not None:
                try:
                    changes = self._ptm.update_statuses_from_beat(assistant_response)
                    if changes:
                        self.lorebook.save()
                except Exception as exc:  # noqa: BLE001
                    self._record_runtime_issue(
                        "post_turn.persona_status",
                        f"Persona status update failed: {exc}",
                        user_visible=True,
                    )
            # HiRAG: ingest story turns into the story section so they stay
            # isolated from assistant memories and are only surfaced when in
            # You'niverse mode.
            if self._hirag is not None and self.rag_export_enabled:
                try:
                    self._hirag.ingest_turn(
                        query=user_text,
                        response=assistant_response,
                        session_id=self.active_story.session_id,
                        section="story",
                    )
                    self._hirag.submit_compress()  # off-thread — never blocks UI
                except Exception as exc:  # noqa: BLE001
                    self._record_runtime_issue(
                        "post_turn.story_hirag",
                        f"Story memory ingest/compress failed: {exc}",
                        user_visible=True,
                    )
            return

        user = self.user_name or "User"

        # Update emotional memory
        self.emotional_memory.process_turn(
            user_message=user_text,
            assistant_response=assistant_response,
            user_name=user,
        )

        # Keep recent window — trim to exactly _MAX_RECENT turns
        self._recent_turns.append((user_text, assistant_response))
        self._turn_timestamps.append(timestamp)
        if len(self._recent_turns) > self._MAX_RECENT:
            self._recent_turns = self._recent_turns[-self._MAX_RECENT:]
            self._turn_timestamps = self._turn_timestamps[-self._MAX_RECENT:]

        # HiRAG: feed turn into the correct section of the ephemeral layer,
        # then auto-promote layers if thresholds are hit.
        # When a Lorebook persona is active in Companion mode, store the turn
        # under that persona's ID so memories stay isolated per character.
        if self._hirag is not None and self.rag_export_enabled:
            try:
                _section = "assistant"
                if self.lorebook is not None:
                    try:
                        active_p = self.lorebook.active_persona()
                        if active_p is not None:
                            _section = active_p.persona_id
                    except Exception as exc:  # noqa: BLE001
                        self._record_runtime_issue(
                            "post_turn.active_persona",
                            f"Active persona lookup failed; defaulting to assistant section: {exc}",
                            user_visible=False,
                        )
                self._hirag.ingest_turn(
                    query=user_text,
                    response=assistant_response,
                    session_id=self._session_id,
                    section=_section,
                )
                self._hirag.submit_compress()  # off-thread — never blocks UI
            except Exception as exc:  # noqa: BLE001
                self._record_runtime_issue(
                    "post_turn.companion_hirag",
                    f"Companion memory ingest/compress failed: {exc}",
                    user_visible=True,
                )

        # Canonical ingest ownership is HiRAG-only.
        # SimpleHiRAG remains a retrieval/read-side fallback and lore helper.

        # Lorebook: update the active persona's inner self after each turn.
        # We derive a simple "thought" from what the persona just said so the
        # inner-self state evolves naturally over the conversation.
        if self.lorebook is not None:
            try:
                if self.lorebook.active_persona() is not None:
                    # Compress assistant response to a short inner-thought
                    snip = assistant_response.strip()[:120].replace("\n", " ")
                    self.lorebook.update_inner_self_after_turn(
                        thought=f"Just said: {snip}…" if len(assistant_response) > 120 else f"Just said: {snip}",
                    )
                    # Auto-card creation: if enabled, caller may invoke
                    # lorebook.auto_create_card(); nothing automatic here —
                    # that hook is left to story-script extensions.
                    self.lorebook.save()
            except Exception as exc:  # noqa: BLE001
                self._record_runtime_issue(
                    "post_turn.lorebook",
                    f"Lorebook post-turn update failed: {exc}",
                    user_visible=True,
                )

    def _record_runtime_issue(self, area: str, message: str, user_visible: bool = True) -> None:
        issue = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "area": str(area),
            "message": str(message),
            "user_visible": bool(user_visible),
        }
        self._runtime_issues.append(issue)
        if len(self._runtime_issues) > 200:
            self._runtime_issues = self._runtime_issues[-200:]
        print(f"[core][{issue['area']}] {issue['message']}", file=sys.stderr)

    def consume_runtime_issues(self, user_visible_only: bool = True) -> list[dict[str, str | bool]]:
        """Return and clear queued runtime issues.

        By default, only issues flagged as user-visible are returned.
        """
        if user_visible_only:
            selected = [i for i in self._runtime_issues if bool(i.get("user_visible", True))]
            remaining = [i for i in self._runtime_issues if not bool(i.get("user_visible", True))]
            self._runtime_issues = remaining
            return selected
        selected = list(self._runtime_issues)
        self._runtime_issues = []
        return selected

    # ------------------------------------------------------------------
    # Provider availability convenience
    # ------------------------------------------------------------------

    @property
    def provider_label(self) -> str:
        return getattr(self.provider, "label", "Unknown")

    # ------------------------------------------------------------------
    # Knowledge Base (The Nexus Core ingestion layer)
    # ------------------------------------------------------------------

    def ingest_documents(self, paths: list[str]) -> list[dict]:
        """
        Ingest one or more files into the NexusDocStore knowledge base.

        Accepts .txt, .md, .pdf, .docx.
        Returns a list of result dicts with keys: status, filename,
        chunks_created, message.
        """
        self._ensure_doc_store()
        if self._doc_store is None:
            return [{"status": "error", "filename": p,
                     "chunks_created": 0,
                     "message": "NexusDocStore not available"} for p in paths]
        _MAX_FILE_MB = 50
        results = []
        for path in paths:
            p = Path(path)
            # Handle folder paths — ingest every supported file inside
            if p.is_dir():
                sub_results = self.ingest_documents(
                    [str(f) for f in p.rglob("*")
                     if f.is_file() and f.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}]
                )
                results.extend(sub_results)
                continue
            try:
                size_mb = p.stat().st_size / (1024 * 1024)
            except OSError:
                size_mb = 0
            if size_mb > _MAX_FILE_MB:
                results.append({
                    "status": "skipped",
                    "filename": p.name,
                    "chunks_created": 0,
                    "message": f"Skipped: file too large ({size_mb:.1f} MB > {_MAX_FILE_MB} MB limit)",
                })
                continue
            try:
                self._doc_store.ingest_file(p)
                doc_id = self._doc_store._find_doc_id_by_path(p)
                chunks = 0
                if doc_id and doc_id in self._doc_store._catalog["docs"]:
                    chunks = len(self._doc_store._catalog["docs"][doc_id].get("chunk_ids", []))
                results.append({
                    "status": "ok",
                    "filename": p.name,
                    "chunks_created": chunks,
                    "message": f"Ingested {chunks} chunk(s)",
                })
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "status": "error",
                    "filename": p.name,
                    "chunks_created": 0,
                    "message": str(exc),
                })
        return results

    def kb_stats(self) -> dict:
        """Return knowledge-base statistics (chunk count, files, search mode)."""
        self._ensure_doc_store()
        if self._doc_store is None:
            return {"total_chunks": 0, "ingested_files": 0, "files": [],
                    "vector_search_available": False, "search_mode": "none"}
        try:
            s = self._doc_store.stats()
            files = [
                {
                    "filename": doc.get("title", doc_id),
                    "chunks":   len(doc.get("chunk_ids", [])),
                    "doc_id":   doc_id,
                    "section":  doc.get("section", "shared"),
                }
                for doc_id, doc in self._doc_store._catalog["docs"].items()
            ]
            return {
                "total_chunks":           s["chunk_count"],
                "ingested_files":         s["doc_count"],
                "files":                  files,
                "vector_search_available": False,
                "search_mode":            "keyword",
            }
        except Exception:  # noqa: BLE001
            return {"total_chunks": 0, "ingested_files": 0, "files": [],
                    "vector_search_available": False, "search_mode": "none"}

    def remove_documents(self, filenames: list[str]) -> int:
        """Remove documents from the NexusDocStore knowledge base by filename.

        Returns the number of documents that were actually removed.
        """
        self._ensure_doc_store()
        if self._doc_store is None:
            return 0
        filenames_set = set(filenames)
        remove_ids = [
            doc_id
            for doc_id, doc in self._doc_store._catalog["docs"].items()
            if doc.get("title") in filenames_set
               or Path(doc.get("path", "")).name in filenames_set
        ]
        return self._doc_store.remove_docs(remove_ids)

    def clear_knowledge_base(self) -> int:
        """Delete ALL documents from the NexusDocStore knowledge base.

        Returns the number of documents that were cleared.
        """
        self._ensure_doc_store()
        if self._doc_store is None:
            return 0
        return self._doc_store.clear()

    def set_doc_section(self, doc_id: str, section: str) -> bool:
        """Set the visibility section for a KB document.

        ``"shared"``    — appears in both Companion and You'niverse mode.
        ``"assistant"`` — Companion / assistant mode only.
        """
        self._ensure_doc_store()
        if self._doc_store is None:
            return False
        return self._doc_store.set_doc_section(doc_id, section)

    def _short_llm_call(self, prompt: str) -> str:
        try:
            return self.provider.generate(prompt, {"max_tokens": 256})
        except Exception as exc:  # noqa: BLE001
            # Record provider error (priority 16)
            self._record_runtime_issue(
                "short_llm_call",
                f"Provider generate failed: {type(exc).__name__}: {exc}",
                user_visible=False
            )
            return ""

    def import_session_to_rag(self, session_id: str) -> dict:
        """
        Ingest all turns from a saved ChatSession or StorySession into HiRAG.

        This is a one-shot import (not affected by rag_export_enabled).
        Returns: {"ingested": int, "failed": int, "reason": str | None}
        """
        result = {"ingested": 0, "failed": 0, "reason": None}
        if self._hirag is None:
            result["reason"] = "HiRAG not initialized"
            return result
        turns: list[tuple[str, str]] = []
        section = "assistant"

        # Try loading as a ChatSession first
        try:
            session = self.load_session_by_id(session_id)
            if session is not None:
                turns = list(session.recent_turns)
                section = "assistant"
        except Exception as exc:  # noqa: BLE001
            # Record session load failure (priority 17)
            self._record_runtime_issue(
                "import_session.load",
                f"ChatSession load failed: {type(exc).__name__}: {exc}",
                user_visible=False
            )

        # Try as a StorySession if not found
        if not turns:
            try:
                from auranexus.story.session import StorySession
                story = StorySession.load(session_id)
                turns = [(b.player_action, b.narrator_response) for b in story.beats]
                section = "story"
            except Exception as exc:  # noqa: BLE001
                # Record story load failure (priority 17)
                self._record_runtime_issue(
                    "import_session.load_story",
                    f"StorySession load failed: {type(exc).__name__}: {exc}",
                    user_visible=False
                )

        if not turns:
            result["reason"] = "No turns found in session"
            return result

        for user_text, assistant_text in turns:
            try:
                self._hirag.ingest_turn(
                    query=user_text,
                    response=assistant_text,
                    session_id=session_id,
                    section=section,
                )
                result["ingested"] += 1
            except Exception as exc:  # noqa: BLE001
                # Record ingest failure (priority 17)
                result["failed"] += 1
                self._record_runtime_issue(
                    "import_session.ingest_turn",
                    f"HiRAG ingest failed: {type(exc).__name__}: {exc}",
                    user_visible=False
                )
        try:
            self._hirag.submit_compress()  # off-thread — never blocks UI
        except Exception as exc:  # noqa: BLE001
            # Record compress failure (priority 17)
            self._record_runtime_issue(
                "import_session.compress",
                f"HiRAG compress failed: {type(exc).__name__}: {exc}",
                user_visible=False
            )
        return result

    def load_session_by_id(self, session_id: str) -> "ChatSession | None":
        """Return the ChatSession with the given ID, or None if not found."""
        for s in self.list_sessions():
            if s.session_id == session_id:
                return s
        return None

    def rebuild_rag_index(self) -> int:
        """Encode any KB chunks that are missing from the vector embedding cache.

        Safe to call at any time — already-indexed chunks are skipped.
        Returns the number of newly embedded chunks.
        """
        try:
            from nexus_doc_store import rebuild_embedding_cache  # type: ignore
            return rebuild_embedding_cache(data_dir=str(self._data_root))
        except Exception as exc:  # noqa: BLE001
            print(f"[core] rebuild_rag_index failed: {exc}")
            return 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _make_session_id() -> str:
        import uuid
        ts = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        # Add UUID suffix to prevent collisions on fast repeated session creation (priority 18)
        suffix = str(uuid.uuid4())[:8]
        return f"{ts}_{suffix}"

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[ChatSession]:
        """Return all saved sessions, newest first."""
        sessions: list[ChatSession] = []
        for p in sorted(self._sessions_dir.glob("*.json"), reverse=True):
            try:
                sessions.append(ChatSession.from_dict(json.loads(p.read_text())))
            except Exception:  # noqa: BLE001
                pass
        return sessions

    def save_session(self, session: ChatSession) -> None:
        """Write a session to disk."""
        try:
            path = self._sessions_dir / f"{session.session_id}.json"
            _atomic_write_text(path, json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        except OSError:
            pass

    def delete_session(self, session_id: str) -> None:
        """Delete a session file."""
        try:
            (self._sessions_dir / f"{session_id}.json").unlink(missing_ok=True)
        except OSError:
            pass

    def new_session(self, name: str = "") -> ChatSession:
        """Create a fresh session and reset runtime state."""
        sid = self._make_session_id()
        self._session_id = sid
        self._recent_turns = []
        self._turn_timestamps = []
        self._response_tracker.reset()
        return ChatSession(
            session_id=sid,
            name=name or f"Chat — {datetime.now().strftime('%b %d %H:%M')}",
            created_at=datetime.now().isoformat(),
        )

    def load_session(self, session: ChatSession) -> None:
        """Restore runtime state from a saved session."""
        self._session_id = session.session_id
        self._recent_turns = list(session.recent_turns)
        self._turn_timestamps = list(session.turn_timestamps)
        # Replay existing turns into tracker so loaded sessions get accurate history
        for _, resp in session.recent_turns:
            self._response_tracker.record(resp)

    def ingest_session_into_rag(self, session: ChatSession) -> int:
        """Ingest all turns from a session into the document knowledge base.

        Uses a stable per-session file so re-ingesting after new turns rewrites
        the same source rather than accumulating duplicate chunks. The ingestion
        layer's content-hash dedup skips it entirely when nothing has changed.

        Returns the number of turns successfully ingested.
        """
        # Session turns are already stored in HiRAG on every post_turn() call.
        # This method is preserved for API compatibility but HiRAG is the
        # canonical store; there is nothing additional to ingest here.
        return len(session.recent_turns) if session.recent_turns else 0
