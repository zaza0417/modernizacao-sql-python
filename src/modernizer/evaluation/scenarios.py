"""Cenarios de teste usados na metrica de equivalencia comportamental."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Scenario:
    routine: str
    label: str
    args: tuple[Any, ...]


def build_scenarios() -> list[Scenario]:
    today = date.today()
    start = today - timedelta(days=40)
    return [
        Scenario("fn_saldo_cliente", "cliente com contas ativas", (1,)),
        Scenario("fn_saldo_cliente", "cliente com conta inativa", (2,)),
        Scenario("fn_saldo_cliente", "cliente inexistente", (999,)),
        Scenario("sp_atualizar_status_contas_inativas", "30 dias", (30,)),
        Scenario("sp_atualizar_status_contas_inativas", "dias invalido", (-1,)),
        Scenario("sp_transferir_entre_contas", "transferencia valida", (1, 3, Decimal("100.00"))),
        Scenario("sp_transferir_entre_contas", "contas iguais", (1, 1, Decimal("10.00"))),
        Scenario("sp_transferir_entre_contas", "saldo insuficiente", (1, 3, Decimal("5000.00"))),
        Scenario("sp_transferir_entre_contas", "conta inativa", (1, 4, Decimal("10.00"))),
        Scenario("sp_transferir_entre_contas", "valor negativo", (1, 3, Decimal("-5.00"))),
        Scenario("sp_transferir_entre_contas", "destino inexistente", (1, 999, Decimal("10.00"))),
        Scenario("sp_processar_lote_taxas", "data com transacoes", (today,)),
        Scenario("sp_processar_lote_taxas", "data sem transacoes", (date(2000, 1, 1),)),
        Scenario("sp_relatorio_mensal_cliente", "periodo de dois meses", (1, start, today)),
        Scenario("sp_relatorio_mensal_cliente", "periodo invertido", (1, today, start)),
        Scenario("sp_relatorio_mensal_cliente", "cliente inexistente", (999, start, today)),
    ]
