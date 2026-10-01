"""Executa o modulo gerado contra um banco de teste, em transacao desfeita."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from modernizer.dialects.base import ParsedProcedure

_SEED_FILE = Path(os.getenv("TEST_SEED_FILE", "samples/seed_teste.sql"))


def _sample_value(sql_type: str) -> Any:
    kind = sql_type.upper()
    if "INT" in kind:
        return 1
    if "DECIMAL" in kind or "NUMERIC" in kind:
        return Decimal("10.00")
    if "DATE" in kind or "TIMESTAMP" in kind:
        return date.today()
    if "BOOL" in kind:
        return True
    return "x"


def check_execution(code: str, parsed: ParsedProcedure) -> list[str] | None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        return None

    namespace: dict[str, Any] = {"__name__": "generated"}
    try:
        exec(compile(code, "generated.py", "exec"), namespace)
    except Exception as exc:
        return [f"execucao: erro ao carregar o modulo: {type(exc).__name__}: {exc}"]

    name = parsed["name"]
    function = namespace[name]
    args = [
        _sample_value(p["type"]) for p in parsed["parameters"] if p["mode"] != "OUT"
    ]
    own_exceptions = tuple(
        value
        for value in namespace.values()
        if isinstance(value, type)
        and issubclass(value, Exception)
        and value.__module__ == "generated"
    )

    try:
        with psycopg.connect(url) as conn:
            with conn.transaction(force_rollback=True):
                if _SEED_FILE.exists():
                    conn.execute(_SEED_FILE.read_text(encoding="utf-8"))
                function(conn, *args)
    except own_exceptions:
        return []
    except Exception as exc:
        detail = str(exc).splitlines()[0] if str(exc) else ""
        return [
            f"execucao: {type(exc).__name__} ao chamar {name}{tuple(args)}: {detail}"
        ]
    return []