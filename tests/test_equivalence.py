import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest

from modernizer.dialects import get_dialect
from modernizer.evaluation.equivalence import as_rows, compare, load_function, original_call
from modernizer.evaluation.service import summarize

SAMPLES = Path("samples")
TEST_DB = os.getenv("TEST_DATABASE_URL")

CORRECT = """
def fn_saldo_cliente(conn, p_cliente_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(saldo), 0) FROM contas"
        " WHERE cliente_id = %(id)s AND status = 'ATIVA'",
        {"id": p_cliente_id},
    ).fetchone()
    return row[0]
"""
WRONG = CORRECT.replace(" AND status = 'ATIVA'", "")


def _parsed(name: str):
    return get_dialect("postgres").parse((SAMPLES / f"{name}.sql").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        ("fn_saldo_cliente", "SELECT fn_saldo_cliente(%s)"),
        (
            "sp_atualizar_status_contas_inativas",
            "CALL sp_atualizar_status_contas_inativas(%s, NULL)",
        ),
        ("sp_transferir_entre_contas", "CALL sp_transferir_entre_contas(%s, %s, %s)"),
        ("sp_relatorio_mensal_cliente", "SELECT * FROM sp_relatorio_mensal_cliente(%s, %s, %s)"),
    ],
)
def test_original_call_is_derived_from_parsing(name, sql):
    assert original_call(_parsed(name)) == sql


def test_as_rows_normalizes_return_shapes():
    @dataclass
    class Row:
        a: int
        b: str

    assert as_rows(None) == []
    assert as_rows(5) == [(5,)]
    assert as_rows(Row(1, "x")) == [(1, "x")]
    assert as_rows([Row(1, "x"), Row(2, "y")]) == [(1, "x"), (2, "y")]
    assert as_rows([(1,)]) == [(1,)]


def test_load_function_returns_callable():
    function = load_function("def f(conn, x):\n    return x * 2\n", "f")
    assert function(None, 21) == 42


def test_summarize_computes_rates():
    results = [
        {"routine": "a", "equivalent": True},
        {"routine": "a", "equivalent": False},
        {"routine": "b", "equivalent": True},
    ]
    summary = summarize(results)
    assert summary["total"] == 3
    assert summary["equivalent"] == 2
    assert summary["by_routine"]["a"] == {"total": 2, "equivalent": 1, "rate": 0.5}


@pytest.mark.skipif(not TEST_DB, reason="requer TEST_DATABASE_URL")
@pytest.mark.parametrize(("code", "expected"), [(CORRECT, True), (WRONG, False)])
def test_compare_against_original_procedure(code, expected):
    seed = (SAMPLES / "seed_teste.sql").read_text(encoding="utf-8")
    with psycopg.connect(TEST_DB) as conn:
        result = compare(conn, seed, _parsed("fn_saldo_cliente"), code, (2,))
    assert result["equivalent"] is expected
