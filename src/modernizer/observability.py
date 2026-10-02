"""Integracao opcional com o Langfuse: ativa apenas quando as chaves estao configuradas."""

import os
from typing import Any

from langfuse import get_client
from langfuse.langchain import CallbackHandler


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def new_trace_handler() -> CallbackHandler | None:
    """Handler que transforma a execucao do grafo em um trace, com um span por no."""
    return CallbackHandler() if tracing_enabled() else None


def record_generation(model: str, system: str, user: str, result: dict[str, Any]) -> None:
    """Completa o span da chamada ao LLM com modelo, prompt, resposta e tokens."""
    if not tracing_enabled():
        return
    get_client().update_current_generation(
        model=model,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        output=result["code"],
        usage_details={"input": result["input_tokens"], "output": result["output_tokens"]},
    )


def score_trace(handler: CallbackHandler | None, result: dict[str, Any]) -> None:
    """Registra no trace o desfecho da validacao e o numero de tentativas."""
    if handler is None or not handler.last_trace_id:
        return
    client = get_client()
    errors = (result.get("validation") or {}).get("errors")
    passed = result.get("status") == "sucesso"
    client.create_score(
        trace_id=handler.last_trace_id,
        name="validacao_aprovada",
        value=1.0 if passed else 0.0,
        comment="; ".join(errors or result.get("errors") or []) or None,
    )
    client.create_score(
        trace_id=handler.last_trace_id,
        name="tentativas",
        value=float(result.get("attempts", 0)),
    )
