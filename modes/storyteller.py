from dataclasses import dataclass

from core.guardrails import finish_budget_limited_reply, sanitize_single_reply
from core.runtime import AuraRuntime, PromptContext


@dataclass
class StoryTurnResult:
    prompt_context: PromptContext
    response: str


class StorytellerMode:
    """Storyteller inference path for continuous narrative turns."""

    def __init__(self, runtime: AuraRuntime) -> None:
        self.runtime = runtime

    def _collect_text(self, prompt: str) -> str:
        return "".join(self.runtime.inference_engine.generate(prompt)).strip()

    def generate_turn(self, user_input: str) -> StoryTurnResult:
        self.runtime.set_mode("storyteller")
        context = self.runtime.build_prompt(user_input)
        response = sanitize_single_reply(
            self._collect_text(context.prompt),
            user_name=self.runtime.user_name,
            assistant_name=self.runtime.aura_name,
            extra_turn_speakers=(
                self.runtime.active_story.player_name,
                self.runtime.active_story.narrator_name,
            ) if self.runtime.active_story is not None else None,
        )
        if getattr(self.runtime.inference_engine, "last_generation_hit_budget", False):
            response = finish_budget_limited_reply(response)
        self.runtime.post_turn(user_input, response)
        return StoryTurnResult(prompt_context=context, response=response)
