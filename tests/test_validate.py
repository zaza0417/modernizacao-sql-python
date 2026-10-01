from modernizer.nodes.validate import validate_node

PARSED = {"name": "fn_x", "parameters": []}
GOOD = '"""Modulo."""\n\n\ndef fn_x(conn):\n    return 1\n'


def _validate(code: str, monkeypatch) -> dict:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    return validate_node({"generated_code": code, "parsed": PARSED})


def test_valid_module_passes(monkeypatch):
    result = _validate(GOOD, monkeypatch)
    assert result["status"] == "sucesso"
    assert result["validation"]["errors"] == []


def test_syntax_error_is_reported(monkeypatch):
    result = _validate("def fn_x(conn:\n", monkeypatch)
    assert result["status"] == "parcial"
    assert result["validation"]["checks"] == {"syntax": False}


def test_docstring_after_imports_is_rejected(monkeypatch):
    code = 'import os\n"""Modulo."""\n\n\ndef fn_x(conn):\n    return os.sep\n'
    errors = _validate(code, monkeypatch)["validation"]["errors"]
    assert any("docstring" in e for e in errors)


def test_missing_main_function_is_rejected(monkeypatch):
    code = '"""Modulo."""\n\n\ndef outra(conn):\n    return 1\n'
    errors = _validate(code, monkeypatch)["validation"]["errors"]
    assert any("fn_x" in e for e in errors)


def test_first_parameter_must_be_conn(monkeypatch):
    code = '"""Modulo."""\n\n\ndef fn_x(p_id):\n    return p_id\n'
    errors = _validate(code, monkeypatch)["validation"]["errors"]
    assert any("conn" in e for e in errors)


def test_unused_import_is_caught_by_lint(monkeypatch):
    code = '"""Modulo."""\n\nimport os\n\n\ndef fn_x(conn):\n    return 1\n'
    result = _validate(code, monkeypatch)
    assert result["validation"]["checks"]["lint"] is False
