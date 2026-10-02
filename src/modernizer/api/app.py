from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from modernizer.evaluation.service import run_evaluation
from modernizer.graph.builder import graph
from modernizer.observability import new_trace_handler, score_trace

app = FastAPI(title="Modernizer")


class ModernizeRequest(BaseModel):
    source_code: str
    schema_ddl: str | None = None
    dialect: str = "postgres"


class ModernizeResponse(BaseModel):
    id: str | None
    status: str
    generated_code: str | None
    report: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/modernize")
def modernize(request: ModernizeRequest) -> ModernizeResponse:
    handler = new_trace_handler()
    config = {"run_name": "modernize", "callbacks": [handler] if handler else []}
    result = graph.invoke(request.model_dump(), config=config)
    score_trace(handler, result)
    return ModernizeResponse(
        id=result.get("execution_id"),
        status=result["status"],
        generated_code=result.get("generated_code"),
        report=result["report"],
    )


@app.post("/evaluate")
def evaluate() -> dict[str, Any]:
    """Roda a metrica de equivalencia sobre a ultima geracao de cada rotina."""
    return run_evaluation()
