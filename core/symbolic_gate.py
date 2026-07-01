"""
SymbolicGate — deterministic intent classifier for companion prompt routing.

Sits between raw user input and the LLM call. In < 1 ms it decides:
  - Intent category  (what kind of message this is)
  - RAG plan         (which memory sources to query, if any)
  - Tool access      (whether tools should appear in the prompt)
  - Skill            (which prompt focus/tone to use)

Rules are evaluated top-to-bottom; first match wins. This makes the logic
fully auditable, debuggable, and extensible without any ML retraining.

Ported and adapted from AuraNexus.old/auranexus/engine/symbolic_gate.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


# ── Decision vocabulary ────────────────────────────────────────────────────────

class Intent(Enum):
    """What the user is trying to do."""
    FACTUAL        = auto()   # "what is X / tell me about Y / how does Z work"
    MEMORY_RECALL  = auto()   # "do you remember / what did we say / earlier you said"
    EMOTIONAL      = auto()   # venting, feelings, personal support
    CREATIVE       = auto()   # story, roleplay, "write me / imagine / describe"
    ACTION         = auto()   # explicit tool request: "find file / run / search"
    CONVERSATIONAL = auto()   # greetings, chit-chat — no deep processing needed


class RAGPlan(Enum):
    """Which retrieval sources to query."""
    NONE       = auto()   # skip all RAG — pure LLM response
    KB_ONLY    = auto()   # only the document knowledge base
    HIRAG_ONLY = auto()   # only HiRAG conversation memory
    BOTH       = auto()   # KB first, HiRAG fallback


class ToolAccess(Enum):
    """Whether to expose tools in the prompt."""
    BLOCKED  = auto()   # strip tool descriptions — LLM cannot use tools
    ALLOWED  = auto()   # tools available but not required
    REQUIRED = auto()   # user explicitly asked for a tool action


class Skill(Enum):
    """Which prompt focus / tone to use for the LLM call."""
    COMPANION  = auto()   # warm conversation
    RAG_ANSWER = auto()   # info delivery — answer from sources
    MEMORY     = auto()   # reflection on past conversation
    CREATIVE   = auto()   # imaginative / narrative
    TOOL       = auto()   # action execution


# ── Decision record ────────────────────────────────────────────────────────────

@dataclass
class GateDecision:
    intent:      Intent
    rag_plan:    RAGPlan
    tool_access: ToolAccess
    skill:       Skill
    reason:      str = ""

    def allows_rag(self) -> bool:
        return self.rag_plan != RAGPlan.NONE

    def use_hirag(self) -> bool:
        return self.rag_plan in (RAGPlan.HIRAG_ONLY, RAGPlan.BOTH)

    def blocks_tools(self) -> bool:
        return self.tool_access == ToolAccess.BLOCKED


# ── Pattern sets ──────────────────────────────────────────────────────────────

# Short exact-match conversational fillers — no retrieval needed.
_CONVERSATIONAL_EXACT: frozenset[str] = frozenset({
    "hi", "hello", "hey", "yo", "sup",
    "test", "testing", "ping",
    "thanks", "thank", "thank you", "ty", "thx",
    "ok", "okay", "k", "sure", "yep", "yes", "yeah", "yup",
    "no", "nope", "nah",
    "lol", "haha", "hehe", "lmao",
    "bye", "goodbye", "cya", "see you",
    "good morning", "good afternoon", "good evening", "good night",
    "how are you", "how are you doing", "what's up", "whats up",
    "i see", "got it", "understood", "makes sense", "alright",
})

# Memory recall — user refers to something from earlier in the session.
_MEMORY_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bdo you remember\b",
        r"\byou (?:said|mentioned|told me)\b",
        r"\bearlier (you|we|i)\b",
        r"\bwe (?:talked|discussed|were talking)\b",
        r"\blast time\b",
        r"\bwhat did (i|we|you) say\b",
        r"\bremind me\b",
        r"\bwhat did you mean\b",
    ]
]

# Emotional — user is expressing feelings or seeking support.
_EMOTIONAL_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bi(?:'m| am) (?:feeling|sad|upset|angry|anxious|depressed|stressed|worried|scared|lonely|tired|exhausted|overwhelmed|happy|excited|proud|grateful)\b",
        r"\bi feel\b",
        r"\bthis is (?:hard|difficult|tough|overwhelming)\b",
        r"\bi (?:can't|cannot) (?:stop|help)\b",
        r"\bno one (?:understands|cares|listens)\b",
        r"\bi need (?:support|help|someone to talk)\b",
        r"\bi(?:'ve| have) been (?:struggling|dealing with|going through)\b",
    ]
]

# Creative — story/roleplay/writing requests.
_CREATIVE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:write|create|generate|make up|craft)\b.{0,40}\b(?:story|poem|scene|chapter|narrative|tale|fiction)\b",
        r"\bimagine\b",
        r"\blet(?:'s| us) (?:roleplay|play|pretend|imagine)\b",
        r"\bcontinue the story\b",
        r"\bwhat (?:happens|would happen) (?:next|if)\b",
        r"\bin character\b",
        r"\bact (?:as|like)\b",
        r"\bdescribe.{0,30}\b(?:scene|setting|character|world)\b",
    ]
]

# Action / tool — user wants the AI to do something on the machine.
_ACTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:search|find|look up|look for)\b.{0,20}\b(?:file|folder|directory|on my|on the)\b",
        r"\b(?:run|execute|open|launch|start)\b.{0,20}\b(?:program|app|script|command|terminal)\b",
        r"\blist (?:my |the )?(?:files|folders|directory)\b",
        r"\bread (?:the |this )?file\b",
        r"\b(?:download|install|update)\b",
        r"\bweb search\b",
        r"\bcheck (?:the |my )?(?:weather|news|calendar|clock|time)\b",
    ]
]

# Factual — knowledge questions.
_FACTUAL_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:what|who|where|when|why|how|which|explain|describe|tell me about|define)\b",
        r"\b(?:what is|what are|who is|who are|how does|how do|how can|how to)\b",
        r"\b(?:give me|show me|list|compare|difference between|advantages of|how many)\b",
    ]
]


def _words(text: str) -> list[str]:
    return [w for w in text.lower().split() if len(w) > 1]


# ── SymbolicGate ───────────────────────────────────────────────────────────────

class SymbolicGate:
    """
    Deterministic intent classifier and prompt strategy planner.

    Call ``decide(user_text, tools_enabled)`` before building an LLM prompt.
    The returned ``GateDecision`` tells ``_build_companion_prompt`` exactly
    which context sections to include.
    """

    def decide(self, user_text: str, tools_enabled: bool = True) -> GateDecision:
        text  = user_text.strip()
        lower = text.lower().rstrip("?!.,;:")
        words = _words(text)

        # Rule 1: Conversational filler ──────────────────────────────────────
        if lower in _CONVERSATIONAL_EXACT or len(words) <= 2:
            return GateDecision(
                intent=Intent.CONVERSATIONAL,
                rag_plan=RAGPlan.NONE,
                tool_access=ToolAccess.BLOCKED,
                skill=Skill.COMPANION,
                reason="conversational filler — skip retrieval and tools",
            )

        # Rule 2: Memory recall ───────────────────────────────────────────────
        if any(p.search(text) for p in _MEMORY_PATTERNS):
            return GateDecision(
                intent=Intent.MEMORY_RECALL,
                rag_plan=RAGPlan.HIRAG_ONLY,
                tool_access=ToolAccess.BLOCKED,
                skill=Skill.MEMORY,
                reason="memory recall — query HiRAG history only",
            )

        # Rule 3: Emotional support ───────────────────────────────────────────
        if any(p.search(text) for p in _EMOTIONAL_PATTERNS):
            return GateDecision(
                intent=Intent.EMOTIONAL,
                rag_plan=RAGPlan.NONE,
                tool_access=ToolAccess.BLOCKED,
                skill=Skill.COMPANION,
                reason="emotional — suppress retrieval and tools, stay present",
            )

        # Rule 4: Explicit action / tool request ─────────────────────────────
        if tools_enabled and any(p.search(text) for p in _ACTION_PATTERNS):
            return GateDecision(
                intent=Intent.ACTION,
                rag_plan=RAGPlan.NONE,
                tool_access=ToolAccess.REQUIRED,
                skill=Skill.TOOL,
                reason="action request — route to tool skill",
            )

        # Rule 5: Creative / story ────────────────────────────────────────────
        if any(p.search(text) for p in _CREATIVE_PATTERNS):
            return GateDecision(
                intent=Intent.CREATIVE,
                rag_plan=RAGPlan.NONE,
                tool_access=ToolAccess.BLOCKED,
                skill=Skill.CREATIVE,
                reason="creative request — pure LLM generation, no retrieval noise",
            )

        # Rule 6: Factual / knowledge question ───────────────────────────────
        if any(p.search(text) for p in _FACTUAL_PATTERNS) or len(words) >= 5:
            return GateDecision(
                intent=Intent.FACTUAL,
                rag_plan=RAGPlan.BOTH,
                tool_access=ToolAccess.BLOCKED if not tools_enabled else ToolAccess.ALLOWED,
                skill=Skill.RAG_ANSWER,
                reason="factual question — query KB then HiRAG",
            )

        # Default: general companion with light retrieval ─────────────────────
        return GateDecision(
            intent=Intent.CONVERSATIONAL,
            rag_plan=RAGPlan.BOTH,
            tool_access=ToolAccess.ALLOWED if tools_enabled else ToolAccess.BLOCKED,
            skill=Skill.COMPANION,
            reason="default companion + retrieval",
        )
