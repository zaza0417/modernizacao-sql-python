from typing import Protocol, TypedDict


class GenerationResult(TypedDict):
    code: str
    decisions: list[str]
    model: str
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    def generate(self, system: str, user: str) -> GenerationResult: ...