from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    # entrada
    source_code: str
    schema_ddl: str | None
    dialect: str
    # saída de cada nó
    parsed: dict[str, Any]
    analysis: dict[str, Any]
    generated_code: str | None
    validation: dict[str, Any]
    generation: dict[str, Any]
    # controle
    attempts: int
    errors: list[str]
    status: str
    report: dict[str, Any]
    execution_id: str