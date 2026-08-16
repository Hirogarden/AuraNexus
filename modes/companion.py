from dataclasses import dataclass

from core.guardrails import finish_budget_limited_reply, sanitize_single_reply
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
            "[Hidden Inner-Self Reflection — private notes only, never shown to user]\n"
            f"Before replying to {self.runtime.user_name}, write up to {self.reflection_tokens} tokens of "
            "private notes: intent, emotional read, tone, what to avoid. "
            "Output ONLY the notes. Do NOT write the reply. Do NOT simulate dialogue. "
            "Notes end with a single blank line."
        )

    def _build_final_prompt(self, context: PromptContext, hidden_reflection: str) -> str:
        prompt_body = self.runtime.strip_response_cue(context.prompt, self.runtime.aura_name)
        reflection_block = hidden_reflection.strip() or "Stay grounded, calm, and direct."
        return (
            f"{prompt_body}\n\n"
            "[Hidden Inner-Self Reflection — use this to shape your reply, do not reveal it]\n"
            f"{reflection_block}\n\n"
            f"Now write your single reply to {self.runtime.user_name}. "
            "One reply only. Stop the moment you finish your last sentence.\n\n"
            f"{self.runtime.aura_name}:"
        )

    def _sanitize_response(self, response: str) -> str:
        cleaned = sanitize_single_reply(
            response,
            user_name=self.runtime.user_name,
            assistant_name=self.runtime.aura_name,
        )
        if getattr(self.runtime.inference_engine, "last_generation_hit_budget", False):
            return finish_budget_limited_reply(cleaned)
        return cleaned

    def generate_turn(self, user_input: str) -> CompanionTurnResult:
        self.runtime.set_mode("companion")
        context = self.runtime.build_prompt(user_input)
        reflection_prompt = self._build_reflection_prompt(context, user_input)
        hidden_reflection = sanitize_single_reply(
            self._collect_text(reflection_prompt),
            user_name=self.runtime.user_name,
            assistant_name=self.runtime.aura_name,
        )
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
