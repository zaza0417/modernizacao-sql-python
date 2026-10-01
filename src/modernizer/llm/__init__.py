from functools import lru_cache

from modernizer.llm.base import LLMProvider
from modernizer.llm.gemini_provider import GeminiProvider


@lru_cache
def get_llm() -> LLMProvider:
    return GeminiProvider()