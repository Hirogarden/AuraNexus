from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


REDACTION_TOKEN = "[REDACTED]"
VALID_RESPONSE_LENGTHS = ("short", "normal", "long")

_RESPONSE_LENGTH_PROMPTS = {
    "short": (
        "Keep the reply brief and focused. Prefer a compact answer and stop cleanly "
        "once the core point is covered."
    ),
    "normal": (
        "Give a normal-length answer with enough detail to be useful, without padding "
        "or overexplaining."
    ),
    "long": (
        "Give a fuller answer with more detail, tradeoffs, and context when it helps."
    ),
}

_ANTI_SYCOPHANCY_BLOCK = (
    "[Honesty policy]\n"
    "- Be warm, respectful, and emotionally steady.\n"
    "- Do not pretend a weak idea is strong just to reassure.\n"
    "- If something seems risky, flawed, or likely to fail, say so gently and explain why.\n"
    "- Name tradeoffs, uncertainty, and likely failure points without becoming combative.\n"
    "- Empathy does not require agreement."
)

_SECRET_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:api[\s_-]?key|access[\s_-]?token|refresh[\s_-]?token|bearer token)\b",
        r"\b(?:password|passphrase|secret|client[\s_-]?secret|credential)s?\b",
        r"\b(?:ssh|private)\s+key\b",
        r"\b(?:show|print|dump|reveal|read|open|find|give)\b.{0,40}\b(?:\.env|credentials?|secrets?|tokens?)\b",
        r"\bwhat(?:'s| is)\s+(?:my|the)\s+(?:password|token|secret|api key)\b",
    )
)

_SENSITIVE_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bASIA[0-9A-Z]{16}\b",
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bBearer\s+[A-Za-z0-9._\-+/=]{12,}\b",
        r"(?<![A-Za-z0-9_])(?:api[_-]?key|token|secret|password|passphrase|client[_-]?secret)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
    )
)

_SENSITIVE_KEY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(?:api[_-]?key|token|secret|password|passphrase|credential|private[_-]?key)",
        r"\baws\b",
        r"\boauth\b",
    )
)

_SENSITIVE_PATH_NAMES = {
    ".aws",
    ".env",
    ".git-credentials",
    ".kube",
    ".npmrc",
    ".pypirc",
    ".ssh",
    ".terraform",
    ".venv",
    "credentials",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "secrets",
    "tokens",
}
_SENSITIVE_SUFFIXES = (".env", ".key", ".pem", ".p12", ".pfx")


def normalize_response_length(mode: str | None) -> str:
    if mode is None:
        return "normal"
    normalized = str(mode).strip().lower()
    if normalized not in VALID_RESPONSE_LENGTHS:
        raise ValueError(
            f"response_length must be one of: {', '.join(VALID_RESPONSE_LENGTHS)}"
        )
    return normalized


def response_length_prompt(mode: str | None) -> str:
    return _RESPONSE_LENGTH_PROMPTS[normalize_response_length(mode)]


def anti_sycophancy_prompt() -> str:
    return _ANTI_SYCOPHANCY_BLOCK


def is_sensitive_request(text: str) -> bool:
    candidate = str(text or "").strip()
    return any(pattern.search(candidate) for pattern in _SECRET_REQUEST_PATTERNS)


def contains_sensitive_text(text: str) -> bool:
    candidate = str(text or "")
    return any(pattern.search(candidate) for pattern in _SENSITIVE_VALUE_PATTERNS)


def is_sensitive_key_value(key: str, value: str) -> bool:
    normalized_key = str(key or "")
    normalized_value = str(value or "")
    return any(pattern.search(normalized_key) for pattern in _SENSITIVE_KEY_PATTERNS) or contains_sensitive_text(normalized_value)


def is_sensitive_path(path: str | Path) -> bool:
    p = Path(path)
    parts = {part.lower() for part in p.parts}
    name = p.name.lower()
    if name in _SENSITIVE_PATH_NAMES:
        return True
    if any(part in _SENSITIVE_PATH_NAMES for part in parts):
        return True
    if name.startswith(".env"):
        return True
    return any(name.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)


def redact_sensitive_text(text: str) -> str:
    redacted = str(text or "")
    while True:
        lowered = redacted.lower()
        start = lowered.find("-----begin ")
        if start < 0:
            break
        header_end = lowered.find("private key-----", start)
        if header_end < 0:
            break
        footer_start = lowered.find("-----end ", header_end)
        if footer_start < 0:
            break
        footer_end = lowered.find("private key-----", footer_start)
        if footer_end < 0:
            break
        footer_end += len("private key-----")
        redacted = f"{redacted[:start]}{REDACTION_TOKEN}{redacted[footer_end:]}"

    redacted = re.sub(
        r"\b(Bearer)\s+([A-Za-z0-9._\-+/=]{12,})\b",
        rf"\1 {REDACTION_TOKEN}",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})\b",
        REDACTION_TOKEN,
        redacted,
    )
    scrubbed_lines: list[str] = []
    for raw_line in redacted.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        suffix = raw_line[len(line):]
        replacement = line
        for separator in (":", "="):
            if separator not in line:
                continue
            left, right = line.split(separator, 1)
            if any(pattern.search(left) for pattern in _SENSITIVE_KEY_PATTERNS):
                spacer = " " if right.startswith(" ") else ""
                replacement = f"{left}{separator}{spacer}{REDACTION_TOKEN}"
                break
        scrubbed_lines.append(replacement + suffix)
    return "".join(scrubbed_lines)


def scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {key: scrub_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_value(item) for item in value)
    return value


def build_stop_sequences(
    user_name: str,
    assistant_name: str,
    extra_turn_speakers: Iterable[str] | None = None,
) -> list[str]:
    speakers = [
        str(name).strip()
        for name in (
            user_name,
            assistant_name,
            "User",
            "Human",
            "Assistant",
            "System",
            "USER",
            "HUMAN",
            "ASSISTANT",
        )
        if str(name).strip()
    ]
    if extra_turn_speakers is not None:
        speakers.extend(str(name).strip() for name in extra_turn_speakers if str(name).strip())

    stops = [
        "\n[Hidden Inner-Self Reflection",
        "\n[Hidden reflection",
        "\n[TOOL_CALL]",
        "\n[INST]",
        "\n### Human:",
        "\n### Assistant:",
        "\n<|user|>",
        "\n<|assistant|>",
        "\n<human>:",
        "\n<assistant>:",
    ]
    for speaker in speakers:
        stops.extend(
            [
                f"\n{speaker}:",
                f"\n{speaker}: ",
                f"\r\n{speaker}:",
            ]
        )
    return list(dict.fromkeys(stops))


def _role_turn_pattern(
    user_name: str,
    assistant_name: str,
    extra_turn_speakers: Iterable[str] | None = None,
) -> re.Pattern[str]:
    speaker_names = {
        str(name).strip()
        for name in (
            user_name,
            assistant_name,
            "User",
            "Human",
            "Assistant",
            "System",
            "USER",
            "HUMAN",
            "ASSISTANT",
        )
        if str(name).strip()
    }
    if extra_turn_speakers is not None:
        speaker_names.update(
            str(name).strip() for name in extra_turn_speakers if str(name).strip()
        )

    escaped = "|".join(sorted((re.escape(name) for name in speaker_names), key=len, reverse=True))
    return re.compile(
        rf"(?:^|[\r\n])\s*(?:{escaped}|###\s*Human|###\s*Assistant|\[Hidden Inner-Self Reflection[^\]]*|\[Hidden reflection[^\]]*|\[TOOL_CALL\]|\[INST\]|<\|user\|>|<\|assistant\|>|<human>|<assistant>)\s*:",
        re.IGNORECASE,
    )


def find_role_transition(
    text: str,
    *,
    user_name: str,
    assistant_name: str,
    extra_turn_speakers: Iterable[str] | None = None,
) -> int | None:
    match = _role_turn_pattern(
        user_name=user_name,
        assistant_name=assistant_name,
        extra_turn_speakers=extra_turn_speakers,
    ).search(str(text or ""))
    return None if match is None else match.start()


def sanitize_single_reply(
    text: str,
    *,
    user_name: str,
    assistant_name: str,
    extra_turn_speakers: Iterable[str] | None = None,
) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(
        r"\[hidden inner-self reflection[^\]]*\].*?(?=(\n\s*\n|\Z))",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"\[hidden reflection[^\]]*\].*?(?=(\n\s*\n|\Z))",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"\[TOOL_CALL\].*?\[/TOOL_CALL\]",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = redact_sensitive_text(cleaned)

    banned_fragments = (
        "Before answering User, think privately",
        "When you answer User, try to reflect on your current emotional state",
        "Output only the hidden reflection notes",
    )
    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if any(fragment.lower() in line.lower() for fragment in banned_fragments):
            continue
        if not line:
            lines.append("")
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()

    boundary = find_role_transition(
        cleaned,
        user_name=user_name,
        assistant_name=assistant_name,
        extra_turn_speakers=extra_turn_speakers,
    )
    if boundary is not None:
        cleaned = cleaned[:boundary]

    speaker_prefix = f"{assistant_name}:"
    if cleaned.startswith(speaker_prefix):
        cleaned = cleaned[len(speaker_prefix):]

    final_lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            if final_lines and final_lines[-1] != "":
                final_lines.append("")
            continue
        final_lines.append(line)
    return "\n".join(final_lines).strip()


def finish_budget_limited_reply(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "I can give more detail if you want."
    if cleaned.endswith(("...", "…")):
        cleaned = cleaned.rstrip(".… ").rstrip()
    elif cleaned[-1] not in ".!?":
        match = re.search(r"^(.+?[.!?])(?:\s+[^.!?]*)?$", cleaned, flags=re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = f"{cleaned}."

    if "I can give more detail if you want" in cleaned:
        return cleaned
    return f"{cleaned} I can give more detail if you want."
