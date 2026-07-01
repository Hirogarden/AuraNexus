from dataclasses import dataclass

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
        response = self._collect_text(context.prompt)
        self.runtime.post_turn(user_input, response)
        return StoryTurnResult(prompt_context=context, response=response)
