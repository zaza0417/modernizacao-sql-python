"""Metrica de equivalencia: procedure original x Python gerado, com os mesmos dados."""

from collections.abc import Callable
from dataclasses import astuple, dataclass, is_dataclass
from typing import Any

import psycopg

from modernizer.dialects.base import ParsedProcedure

SNAPSHOT_QUERIES = {
    "contas": "SELECT id, saldo, status FROM contas ORDER BY id",
    "transacoes": "SELECT conta_origem_id, conta_destino_id, tipo, valor, status"
    " FROM transacoes ORDER BY id",
    "log_auditoria": "SELECT entidade, entidade_id, acao, detalhes FROM log_auditoria ORDER BY id",
}

Action = Callable[[psycopg.Connection], Any]


@dataclass
class Outcome:
    rows: list[tuple]
    error: str | None
    state: dict[str, list[tuple]]


def original_call(parsed: ParsedProcedure) -> str:
    """Monta o SQL que invoca a rotina original, a partir do resultado do parsing."""
    name = parsed["name"]
    placeholders = ", ".join("NULL" if p["mode"] == "OUT" else "%s" for p in parsed["parameters"])
    if parsed["kind"] == "PROCEDURE":
        return f"CALL {name}({placeholders})"
    if (parsed["returns"] or "").upper().startswith("TABLE"):
        return f"SELECT * FROM {name}({placeholders})"
    return f"SELECT {name}({placeholders})"


def load_function(code: str, name: str) -> Callable[..., Any]:
    namespace: dict[str, Any] = {"__name__": "generated"}
    exec(compile(code, "generated.py", "exec"), namespace)
    return namespace[name]


def as_rows(value: Any) -> list[tuple]:
    """Normaliza o retorno (None, escalar, dataclass, tupla ou lista) para lista de tuplas."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    rows: list[tuple] = []
    for item in items:
        if is_dataclass(item) and not isinstance(item, type):
            rows.append(astuple(item))
        elif isinstance(item, tuple):
            rows.append(item)
        else:
            rows.append((item,))
    return rows


def _message(exc: Exception) -> str:
    if isinstance(exc, psycopg.Error) and exc.diag.message_primary:
        return exc.diag.message_primary
    return str(exc)


def _run(conn: psycopg.Connection, seed: str, action: Action) -> Outcome:
    rows: list[tuple] = []
    error = None
    with conn.transaction(force_rollback=True):
        conn.execute(seed)
        try:
            with conn.transaction():
                rows = as_rows(action(conn))
        except Exception as exc:
            error = _message(exc)
        state = {table: conn.execute(query).fetchall() for table, query in SNAPSHOT_QUERIES.items()}
    return Outcome(rows, error, state)


def _call_original(sql: str, args: tuple) -> Action:
    def action(conn: psycopg.Connection) -> Any:
        cursor = conn.execute(sql, args)
        return cursor.fetchall() if cursor.description else None

    return action


def compare(
    conn: psycopg.Connection,
    seed: str,
    parsed: ParsedProcedure,
    generated_code: str,
    args: tuple,
) -> dict[str, Any]:
    """Executa original e gerado sobre o mesmo seed e compara retorno, erro e estado."""
    function = load_function(generated_code, parsed["name"])
    original = _run(conn, seed, _call_original(original_call(parsed), args))
    generated = _run(conn, seed, lambda c: function(c, *args))

    if original.error is None and generated.error is None:
        outcome_match = original.rows == generated.rows
    else:
        outcome_match = original.error == generated.error
    state_match = original.state == generated.state
    return {
        "equivalent": outcome_match and state_match,
        "outcome_match": outcome_match,
        "state_match": state_match,
        "original_error": original.error,
        "generated_error": generated.error,
    }
