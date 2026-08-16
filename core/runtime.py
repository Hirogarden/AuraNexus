from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Literal, Optional, Protocol

from core.guardrails import (
    anti_sycophancy_prompt,
    contains_sensitive_text,
    is_sensitive_request,
    redact_sensitive_text,
)
from core.response_tracker import ResponseTracker
from core.symbolic_gate import SymbolicGate, ToolAccess
from storage.chat_session import ChatSession
from storage.emotional_memory import EmotionalMemory
from storage.lorebook import LorebookManager
from storage.story_session import StorySession
from storage.vector_store import LocalVectorStore
from storage.world_state import WorldState


Mode = Literal["companion", "storyteller"]


class ToolSchemaProvider(Protocol):
    def get_tool_schemas(self) -> List[dict[str, Any]]:
        ...


@dataclass
class PromptContext:
    mode: Mode
    prompt: str
    lore_card_ids: List[str]


class AuraRuntime:
    """Lightweight coordinator for mode-specific prompt construction and turn state."""

    def __init__(
        self,
        inference_engine: Any,
        lorebook: LorebookManager | None = None,
        world_state: WorldState | None = None,
        tool_registry: ToolSchemaProvider | None = None,
        aura_name: str = "Aura",
        user_name: str = "User",
        mode: Mode = "companion",
        max_recent_turns: int = 8,
        chat_session_dir: str | Path | None = None,
        story_session_dir: str | Path | None = None,
        emotional_memory_dir: str | Path | None = None,
        hirag_general: LocalVectorStore | None = None,
        hirag_personal: LocalVectorStore | None = None,
    ) -> None:
        if mode not in {"companion", "storyteller"}:
            raise ValueError("Mode must be either 'companion' or 'storyteller'.")

        self.inference_engine = inference_engine
        self.lorebook = lorebook or LorebookManager()
        self.world_state = world_state or WorldState()
        self.tool_registry = tool_registry
        self.aura_name = aura_name.strip() or "Aura"
        self.user_name = user_name.strip() or "User"
        self.mode: Mode = mode
        self.max_recent_turns = max(1, int(max_recent_turns))
        self.recent_turns: List[tuple[str, str]] = []
        self.active_story: StorySession | None = None
        self.active_chat_session: ChatSession | None = None
        self.chat_session_dir = Path(chat_session_dir) if chat_session_dir is not None else None
        self.story_session_dir = Path(story_session_dir) if story_session_dir is not None else None
        if self.chat_session_dir is not None:
            self.chat_session_dir.mkdir(parents=True, exist_ok=True)
        if self.story_session_dir is not None:
            self.story_session_dir.mkdir(parents=True, exist_ok=True)

        # Intent classifier and anti-repetition tracker — zero deps, always active.
        self.symbolic_gate = SymbolicGate()
        self.response_tracker = ResponseTracker()

        # Emotional memory — only created when a writable path is provided.
        self.emotional_memory: Optional[EmotionalMemory] = None
        if emotional_memory_dir is not None:
            self.emotional_memory = EmotionalMemory(base_path=emotional_memory_dir)

        # HiRAG document stores — general is accessible by both modes;
        # personal is exclusive to companion mode.
        self.hirag_general: Optional[LocalVectorStore] = hirag_general
        self.hirag_personal: Optional[LocalVectorStore] = hirag_personal

    def _chat_session_path(self, session_id: str) -> Path:
        if self.chat_session_dir is None:
            raise RuntimeError("Chat session directory is not configured.")
        return self.chat_session_dir / f"{session_id}.json"

    def _story_session_path(self, session_id: str) -> Path:
        if self.story_session_dir is None:
            raise RuntimeError("Story session directory is not configured.")
        return self.story_session_dir / f"{session_id}.json"

    def set_mode(self, mode: Mode) -> None:
        if mode not in {"companion", "storyteller"}:
            raise ValueError("Mode must be either 'companion' or 'storyteller'.")
        self.mode = mode

    def start_story(self, **kwargs: Any) -> StorySession:
        story = StorySession(narrator_name=self.aura_name, **kwargs)
        self.active_story = story
        self.mode = "storyteller"
        if self.story_session_dir is not None:
            story.save(self._story_session_path(story.session_id))
        return story

    def start_chat_session(self, name: str) -> ChatSession:
        session_name = str(name).strip() or f"{self.user_name} Session"
        session_id = datetime.now().strftime("chat_%Y%m%d_%H%M%S")
        session = ChatSession(session_id=session_id, name=session_name)
        self.active_chat_session = session
        self.mode = "companion"
        if self.chat_session_dir is not None:
            session.save(self._chat_session_path(session.session_id))
        return session

    def attach_chat_session(self, session: ChatSession | None) -> None:
        self.active_chat_session = session
        if session is not None:
            self.mode = "companion"

    def attach_story(self, story: StorySession | None) -> None:
        self.active_story = story
        if story is not None:
            self.mode = "storyteller"

    def save_active_chat_session(self) -> Path | None:
        if self.active_chat_session is None or self.chat_session_dir is None:
            return None
        return self.active_chat_session.save(self._chat_session_path(self.active_chat_session.session_id))

    def save_active_story(self) -> Path | None:
        if self.active_story is None or self.story_session_dir is None:
            return None
        return self.active_story.save(self._story_session_path(self.active_story.session_id))

    def list_chat_sessions(self) -> List[dict[str, str]]:
        if self.chat_session_dir is None:
            return []

        sessions: List[dict[str, str]] = []
        for path in sorted(self.chat_session_dir.glob("*.json")):
            loaded = ChatSession.load(path)
            sessions.append(
                {
                    "session_id": loaded.session_id,
                    "name": loaded.name,
                    "created_at": loaded.created_at,
                }
            )
        sessions.sort(key=lambda item: item["created_at"], reverse=True)
        return sessions

    def load_chat_session(self, session_id: str) -> ChatSession:
        session = ChatSession.load(self._chat_session_path(session_id))
        self.attach_chat_session(session)
        return session

    def load_latest_chat_session(self) -> ChatSession | None:
        sessions = self.list_chat_sessions()
        if not sessions:
            return None
        return self.load_chat_session(sessions[0]["session_id"])

    def ensure_chat_session(self, name: str | None = None, restore_latest: bool = True) -> ChatSession:
        if self.active_chat_session is not None:
            return self.active_chat_session

        if restore_latest:
            latest = self.load_latest_chat_session()
            if latest is not None:
                return latest

        return self.start_chat_session(name or f"{self.user_name} Session")

    def list_story_sessions(self) -> List[dict[str, str]]:
        if self.story_session_dir is None:
            return []

        sessions: List[dict[str, str]] = []
        for path in sorted(self.story_session_dir.glob("*.json")):
            loaded = StorySession.load(path)
            sessions.append(
                {
                    "session_id": loaded.session_id,
                    "title": loaded.title,
                    "created_at": loaded.created_at,
                }
            )
        sessions.sort(key=lambda item: item["created_at"], reverse=True)
        return sessions

    def load_story_session(self, session_id: str) -> StorySession:
        story = StorySession.load(self._story_session_path(session_id))
        self.attach_story(story)
        return story

    def get_tool_schemas(self) -> List[dict[str, Any]]:
        if self.tool_registry is None:
            return []
        return self.tool_registry.get_tool_schemas()

    def _build_hirag_block(self, query_text: str, *, include_personal: bool) -> str:
        """Query HiRAG stores and return a formatted context block for prompt injection.

        Companion mode passes include_personal=True to access both buckets.
        Storyteller mode passes include_personal=False to access general only.
        """
        from storage.embedder import embed_text

        MIN_SCORE = 0.15
        fragments: List[str] = []
        if is_sensitive_request(query_text):
            return ""

        if self.hirag_general is not None:
            vec = embed_text(query_text)
            results = self.hirag_general.query_hierarchical(vec, top_k=3, top_clusters=2)
            for doc_text, _meta, score in results:
                if score >= MIN_SCORE and not contains_sensitive_text(doc_text):
                    fragments.append(redact_sensitive_text(doc_text.strip()))

        if include_personal and self.hirag_personal is not None:
            vec = embed_text(query_text)
            results = self.hirag_personal.query_hierarchical(vec, top_k=3, top_clusters=2)
            for doc_text, meta, score in results:
                if (
                    score >= MIN_SCORE
                    and not bool(meta.get("sensitive"))
                    and not contains_sensitive_text(doc_text)
                ):
                    fragments.append(redact_sensitive_text(doc_text.strip()))

        if not fragments:
            return ""
        return "[Retrieved Context]\n" + "\n---\n".join(fragments)

    def _response_length_prompt(self) -> str:
        getter = getattr(self.inference_engine, "get_response_length_prompt", None)
        if callable(getter):
            return getter()
        return "Give a normal-length answer with enough detail to be useful, without padding or overexplaining."

    def _build_companion_prompt(self, user_input: str) -> PromptContext:
        safe_user_input = redact_sensitive_text(user_input)
        lore_cards = self.lorebook.scan_and_retrieve(
            safe_user_input,
            mode="companion",
            persona_id=self.aura_name,
            state_tags={"dialogue", "companion"},
        )
        lore_block = self.lorebook.format_context_block(lore_cards)
        world_block = self.world_state.as_prompt_block()
        history_lines: List[str] = []
        if self.active_chat_session is not None:
            recent_turns = self.active_chat_session.recent_turns(self.max_recent_turns)
            for turn in recent_turns:
                history_lines.append(f"{self.user_name}: {redact_sensitive_text(turn.user_text)}")
                history_lines.append(f"{self.aura_name}: {redact_sensitive_text(turn.assistant_text)}")
        else:
            for prior_user, prior_assistant in self.recent_turns[-self.max_recent_turns:]:
                history_lines.append(f"{self.user_name}: {redact_sensitive_text(prior_user)}")
                history_lines.append(f"{self.aura_name}: {redact_sensitive_text(prior_assistant)}")

        tool_schemas = self.get_tool_schemas()
        tool_names = [schema.get("function", {}).get("name", "") for schema in tool_schemas]

        # Ask the SymbolicGate what this message needs.
        decision = self.symbolic_gate.decide(safe_user_input, tools_enabled=bool(tool_names))

        tools_block = ""
        sensitive_request = is_sensitive_request(safe_user_input)
        if not decision.blocks_tools() and not sensitive_request and tool_names:
            filtered_names = ", ".join(name for name in tool_names if name)
            if filtered_names:
                tools_block = f"[Available tools]\n{filtered_names}"

        persona = (
            f"You are {self.aura_name}, a reflective local AI companion. "
            f"Respond directly to {self.user_name} in one focused reply. "
            f"Do not simulate the conversation continuing after your reply."
        )

        sections = [persona, f"[Response length]\n{self._response_length_prompt()}", anti_sycophancy_prompt()]

        # Emotional context just after the persona.
        if self.emotional_memory is not None:
            emo_block = self.emotional_memory.get_context_block()
            if emo_block:
                sections.append(redact_sensitive_text(emo_block))

        if world_block:
            sections.append(redact_sensitive_text(world_block))
        if lore_block:
            sections.append(redact_sensitive_text(lore_block.strip()))

        # HiRAG retrieved context — companion has access to both buckets.
        hirag_block = self._build_hirag_block(safe_user_input, include_personal=True)
        if hirag_block:
            sections.append(hirag_block)

        if tools_block:
            sections.append(tools_block)

        # Anti-repetition cues immediately before the conversation history.
        sections.append(self.response_tracker.as_prompt_block())
        if sensitive_request:
            sections.append(
                "[Security boundary]\n"
                "Do not help inspect, retrieve, or reveal secrets, credentials, tokens, or private keys."
            )

        if history_lines:
            sections.append("\n".join(history_lines))
        sections.append(f"{self.user_name}: {safe_user_input}")
        sections.append(f"{self.aura_name}:")

        return PromptContext(
            mode="companion",
            prompt="\n\n".join(sections),
            lore_card_ids=[card.id for card in lore_cards],
        )

    def _build_story_prompt(self, user_input: str) -> PromptContext:
        safe_user_input = redact_sensitive_text(user_input)
        if self.active_story is None:
            raise RuntimeError("Storyteller mode requires an active story session.")

        lore_cards = self.lorebook.scan_and_retrieve(
            safe_user_input,
            mode="storyteller",
            state_tags={"narrative", "story"},
        )
        blocks = []
        world_block = self.world_state.as_prompt_block()
        if world_block:
            blocks.append(redact_sensitive_text(world_block))
        lore_block = self.lorebook.format_context_block(lore_cards)
        if lore_block:
            blocks.append(redact_sensitive_text(lore_block.strip()))

        # HiRAG retrieved context — storyteller only accesses the general bucket.
        hirag_block = self._build_hirag_block(safe_user_input, include_personal=False)
        if hirag_block:
            blocks.append(hirag_block)
        blocks.append(f"[Response length]\n{self._response_length_prompt()}")
        blocks.append(anti_sycophancy_prompt())

        return PromptContext(
            mode="storyteller",
            prompt=self.active_story.build_prompt(safe_user_input, extra_system="\n\n".join(blocks)),
            lore_card_ids=[card.id for card in lore_cards],
        )

    def build_prompt(self, user_input: str) -> PromptContext:
        if self.mode == "storyteller":
            return self._build_story_prompt(user_input)
        return self._build_companion_prompt(user_input)

    def post_turn(self, user_input: str, assistant_response: str) -> None:
        if self.mode == "storyteller":
            if self.active_story is None:
                raise RuntimeError("Cannot record storyteller turn without an active story session.")
            self.active_story.add_beat(user_input, assistant_response)
            self.save_active_story()
            return

        self.recent_turns.append((user_input, assistant_response))
        if len(self.recent_turns) > self.max_recent_turns:
            self.recent_turns = self.recent_turns[-self.max_recent_turns:]

        if self.active_chat_session is not None:
            self.active_chat_session.add_turn(user_input, assistant_response)
            self.save_active_chat_session()

        # Record response for anti-repetition tracking.
        self.response_tracker.record(assistant_response)

        # Update emotional memory if configured.
        if self.emotional_memory is not None:
            self.emotional_memory.process_turn(
                user_message=user_input,
                assistant_response=assistant_response,
                user_name=self.user_name,
            )

    @staticmethod
    def strip_response_cue(prompt: str, speaker: str) -> str:
        cue = f"\n\n{speaker}:"
        if prompt.endswith(cue):
            return prompt[: -len(cue)]
        return prompt.rstrip()
