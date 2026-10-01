from pathlib import Path

import pytest

from modernizer.graph.builder import MAX_ATTEMPTS, graph

SOURCE = Path("samples/fn_saldo_cliente.sql").read_text(encoding="utf-8")
GOOD = '"""Modulo."""\n\n\ndef fn_saldo_cliente(conn, p_cliente_id):\n    return p_cliente_id\n'
BAD = "def fn_saldo_cliente(conn:\n"


class FakeLLM:
    def __init__(self, codes: list[str]) -> None:
        self.codes = codes
        self.prompts: list[str] = []

    def generate(self, system: str, user: str) -> dict:
        self.prompts.append(user)
        code = self.codes[min(len(self.prompts), len(self.codes)) - 1]
        return {
            "code": code,
            "decisions": ["d"],
            "model": "fake",
            "input_tokens": 1,
            "output_tokens": 1,
        }


@pytest.fixture
def saved(monkeypatch):
    calls: list[dict] = []

    def fake_save(**kwargs) -> str:
        calls.append(kwargs)
        return "fake-id"

    monkeypatch.setattr("modernizer.nodes.persist.save_execution", fake_save)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    return calls


def _use_llm(monkeypatch, codes: list[str]) -> FakeLLM:
    llm = FakeLLM(codes)
    monkeypatch.setattr("modernizer.nodes.generate.get_llm", lambda: llm)
    return llm


def test_happy_path(monkeypatch, saved):
    _use_llm(monkeypatch, [GOOD])
    result = graph.invoke({"source_code": SOURCE})
    assert result["status"] == "sucesso"
    assert result["attempts"] == 1
    assert result["execution_id"] == "fake-id"
    assert saved[0]["status"] == "sucesso"


def test_retry_sends_errors_back_to_llm(monkeypatch, saved):
    llm = _use_llm(monkeypatch, [BAD, GOOD])
    result = graph.invoke({"source_code": SOURCE})
    assert result["status"] == "sucesso"
    assert result["attempts"] == 2
    assert "Tentativa anterior rejeitada" in llm.prompts[1]


def test_gives_up_after_max_attempts(monkeypatch, saved):
    _use_llm(monkeypatch, [BAD])
    result = graph.invoke({"source_code": SOURCE})
    assert result["status"] == "parcial"
    assert result["attempts"] == MAX_ATTEMPTS
    assert len(saved) == 1


def test_invalid_sql_is_persisted_as_failure(monkeypatch, saved):
    llm = _use_llm(monkeypatch, [GOOD])
    result = graph.invoke({"source_code": "isso nao e sql ("})
    assert result["status"] == "falha"
    assert llm.prompts == []
    assert saved[0]["generated_code"] is None


def test_llm_failure_is_persisted(monkeypatch, saved):
    class Broken:
        def generate(self, system, user):
            raise RuntimeError("sem cota")

    monkeypatch.setattr("modernizer.nodes.generate.get_llm", lambda: Broken())
    result = graph.invoke({"source_code": SOURCE})
    assert result["status"] == "falha"
    assert "sem cota" in result["errors"][0]
    assert len(saved) == 1
