from typing import Any, Protocol, TypedDict


class Parameter(TypedDict):
    name: str
    mode: str          # "IN", "OUT" ou "INOUT"
    type: str


class Variable(TypedDict):
    name: str
    type: str


class ParsedProcedure(TypedDict):
    name: str
    kind: str                  # "FUNCTION" ou "PROCEDURE"
    language: str | None
    parameters: list[Parameter]
    returns: str | None
    variables: list[Variable]
    body_source: str           # texto do corpo, para o prompt
    body_tree: dict[str, Any]  # árvore procedural, para a análise


class Dialect(Protocol):
    name: str

    def parse(self, source: str) -> ParsedProcedure: ...