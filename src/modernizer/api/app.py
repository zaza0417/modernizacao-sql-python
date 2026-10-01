from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from modernizer.graph.builder import graph

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
    result = graph.invoke(request.model_dump())
    return ModernizeResponse(
        id=result.get("execution_id"),
        status=result["status"],
        generated_code=result.get("generated_code"),
        report=result["report"],
    )