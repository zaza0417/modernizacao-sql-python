from typing import Any

from modernizer.db.repository import save_execution
from modernizer.graph.state import PipelineState

_PARSED_FIELDS = ("name", "kind", "language", "parameters", "returns", "variables")


def build_report(state: PipelineState) -> dict[str, Any]:
    parsed = state.get("parsed") or {}
    return {
        "dialect": state.get("dialect", "postgres"),
        "parsing": {k: parsed[k] for k in _PARSED_FIELDS if k in parsed},
        "analysis": state.get("analysis"),
        "generation": state.get("generation"),
        "validation": state.get("validation"),
        "attempts": state.get("attempts", 0),
        "errors": state.get("errors", []),
    }


def persist_node(state: PipelineState) -> dict:
    status = state.get("status") or "falha"
    report = build_report(state)
    try:
        execution_id = save_execution(
            source_code=state.get("source_code", ""),
            generated_code=state.get("generated_code"),
            report=report,
            status=status,
        )
    except Exception as exc:
        errors = [*state.get("errors", []), f"persist: {exc}"]
        return {"report": report, "status": status, "errors": errors}
    return {"report": report, "status": status, "execution_id": execution_id}
