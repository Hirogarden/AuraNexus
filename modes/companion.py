from dataclasses import dataclass
import re

from core.runtime import AuraRuntime, PromptContext


@dataclass
class CompanionTurnResult:
    prompt_context: PromptContext
    hidden_reflection: str
    response: str


class CompanionMode:
    """Companion-mode inference path with a private inner-reflection pass."""

    def __init__(self, runtime: AuraRuntime, reflection_tokens: int = 160) -> None:
        self.runtime = runtime
        self.reflection_tokens = max(32, int(reflection_tokens))

    def _collect_text(self, prompt: str) -> str:
        return "".join(self.runtime.inference_engine.generate(prompt)).strip()

    def _build_reflection_prompt(self, context: PromptContext, user_input: str) -> str:
        prompt_body = self.runtime.strip_response_cue(context.prompt, self.runtime.aura_name)
        return (
            f"{prompt_body}\n\n"
            "[Hidden Inner-Self Reflection]\n"
            f"Before answering {self.runtime.user_name}, think privately about intent, emotional context, pacing, "
            f"and what should remain unsaid. Limit yourself to at most {self.reflection_tokens} tokens. "
            "Do not write the final reply yet. Output only the hidden reflection notes."
        )

    def _build_final_prompt(self, context: PromptContext, hidden_reflection: str) -> str:
        prompt_body = self.runtime.strip_response_cue(context.prompt, self.runtime.aura_name)
        reflection_block = hidden_reflection.strip() or "Stay grounded, calm, and direct."
        return (
            f"{prompt_body}\n\n"
            "[Hidden Inner-Self Reflection - not shown to user]\n"
            f"{reflection_block}\n\n"
            f"Using the hidden reflection above, respond to {self.runtime.user_name} naturally without revealing the reflection.\n\n"
            f"{self.runtime.aura_name}:"
        )

    def _sanitize_response(self, response: str) -> str:
        text = response.strip()
        if not text:
            return ""

        # Remove leaked private blocks that some smaller models may echo verbatim.
        text = re.sub(
            r"\[hidden inner-self reflection[^\]]*\].*?(?=(\n\n|\Z))",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(
            r"\[hidden reflection\s*:\].*?(?=(\n\n|\Z))",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        banned_fragments = (
            "Before answering User, think privately",
            "When you answer User, try to reflect on your current emotional state",
            "Output only the hidden reflection notes",
        )

        clean_lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(fragment.lower() in line.lower() for fragment in banned_fragments):
                continue
            clean_lines.append(line)

        cleaned = "\n".join(clean_lines).strip()

        # Trim accidental speaker prefix when the model starts by echoing "Aura:".
        aura_prefix = f"{self.runtime.aura_name}:"
        if cleaned.startswith(aura_prefix):
            cleaned = cleaned[len(aura_prefix):].strip()

        # If the model starts simulating multi-turn dialogue, keep only Aura's first reply.
        turn_markers = (
            f"\n{self.runtime.user_name}:",
            "\nUser:",
            "\nHuman:",
            "\nUSER:",
        )
        cut_index = min(
            (cleaned.find(marker) for marker in turn_markers if marker in cleaned),
            default=-1,
        )
        if cut_index != -1:
            cleaned = cleaned[:cut_index].strip()

        return cleaned

    def generate_turn(self, user_input: str) -> CompanionTurnResult:
        self.runtime.set_mode("companion")
        context = self.runtime.build_prompt(user_input)
        reflection_prompt = self._build_reflection_prompt(context, user_input)
        hidden_reflection = self._collect_text(reflection_prompt)
        final_prompt = self._build_final_prompt(context, hidden_reflection)
        response = self._sanitize_response(self._collect_text(final_prompt))
        if not response:
            response = "I hear you. I can keep this simple and stay with you one step at a time."
        self.runtime.post_turn(user_input, response)
        return CompanionTurnResult(
            prompt_context=context,
            hidden_reflection=hidden_reflection,
            response=response,
        )
