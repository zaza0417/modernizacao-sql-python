import logging
import os
import time

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from modernizer.llm.base import GenerationResult

logger = logging.getLogger(__name__)

_DEFAULT_MODELS = "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash-preview,gemini-3.5-flash-lite"
_TIMEOUT_MS = 60_000
_ROUNDS = 2


class _Output(BaseModel):
    code: str
    decisions: list[str]


class GeminiProvider:
    def __init__(self, models: str | None = None) -> None:
        raw = models or os.getenv("MODERNIZER_MODEL", _DEFAULT_MODELS)
        self.models = [m.strip() for m in raw.split(",") if m.strip()]
        self._client = genai.Client(
            http_options=types.HttpOptions(timeout=_TIMEOUT_MS)
        )

    def generate(self, system: str, user: str) -> GenerationResult:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=_Output,
        )

        last_error: Exception | None = None
        for attempt in range(_ROUNDS):
            for model in self.models:
                try:
                    response = self._client.models.generate_content(
                        model=model, contents=user, config=config
                    )
                except errors.ClientError as exc:
                    if exc.code != 429:
                        raise
                    logger.warning("modelo %s sem cota: tentando o proximo", model)
                    last_error = exc
                    continue
                except Exception as exc:
                    logger.warning("modelo %s falhou: %s", model, str(exc)[:120])
                    last_error = exc
                    continue
                return self._to_result(response, model)
            time.sleep(2 ** attempt)

        raise RuntimeError(f"Todos os modelos falharam: {last_error}")

    @staticmethod
    def _to_result(response, model: str) -> GenerationResult:
        if not response.text:
            raise RuntimeError("O modelo nao devolveu conteudo")
        output = _Output.model_validate_json(response.text)
        usage = response.usage_metadata
        return {
            "code": output.code,
            "decisions": output.decisions,
            "model": model,
            "input_tokens": usage.prompt_token_count or 0,
            "output_tokens": usage.candidates_token_count or 0,
        }