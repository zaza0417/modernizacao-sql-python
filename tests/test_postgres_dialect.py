from pathlib import Path

import pytest

from modernizer.dialects import get_dialect

SAMPLES = Path("samples")
EXPECTED_RISKS = {
    "fn_saldo_cliente": {"DECIMAL"},
    "sp_atualizar_status_contas_inativas": {"OUT_PARAMS", "ROW_COUNT", "RAISE"},
    "sp_transferir_entre_contas": {"EXCEPTION_BLOCK", "ROW_LOCK", "MULTI_WRITE"},
    "sp_processar_lote_taxas": {"CURSOR_LOOP", "MULTI_WRITE", "JSONB"},
    "sp_relatorio_mensal_cliente": {"RECURSIVE_CTE", "SET_RETURNING", "NESTED_CALL"},
}


def _parse(name: str):
    dialect = get_dialect("postgres")
    return dialect, dialect.parse((SAMPLES / f"{name}.sql").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", EXPECTED_RISKS)
def test_parse_extracts_name(name):
    _, parsed = _parse(name)
    assert parsed["name"] == name
    assert parsed["language"] == "plpgsql"


def test_parse_detects_out_parameter():
    _, parsed = _parse("sp_atualizar_status_contas_inativas")
    modes = {p["name"]: p["mode"] for p in parsed["parameters"]}
    assert modes == {"p_dias": "IN", "p_afetadas": "OUT"}


def test_parse_lists_only_declared_variables():
    _, parsed = _parse("sp_processar_lote_taxas")
    names = [v["name"] for v in parsed["variables"]]
    assert len(names) == 10
    assert "cur_transacoes" in names
    assert not any(n.startswith("__") for n in names)


def test_parse_rejects_non_procedure():
    with pytest.raises(ValueError):
        get_dialect("postgres").parse("SELECT 1")


@pytest.mark.parametrize(("name", "risks"), EXPECTED_RISKS.items())
def test_analyze_flags_expected_risks(name, risks):
    dialect, parsed = _parse(name)
    found = {r["code"] for r in dialect.analyze(parsed)["risks"]}
    assert risks <= found


def test_analyze_cursor_risk_only_on_cursor_procedure():
    for name in EXPECTED_RISKS:
        dialect, parsed = _parse(name)
        codes = {r["code"] for r in dialect.analyze(parsed)["risks"]}
        assert ("CURSOR_LOOP" in codes) == (name == "sp_processar_lote_taxas")


def test_analyze_finds_nested_function_call():
    dialect, parsed = _parse("sp_relatorio_mensal_cliente")
    assert dialect.analyze(parsed)["function_calls"] == ["fn_saldo_cliente"]


def test_unknown_dialect():
    with pytest.raises(ValueError):
        get_dialect("cobol")
