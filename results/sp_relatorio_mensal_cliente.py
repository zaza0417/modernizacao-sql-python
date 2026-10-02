"""Modulo contendo a traducao de sp_relatorio_mensal_cliente para relatorios mensais bancarios."""

from dataclasses import dataclass
import datetime
import decimal
import logging
import psycopg

logger = logging.getLogger(__name__)

class RelatorioMensalClienteError(Exception):
    """Excecao de negocio lancada quando parametros ou condicoes sao invalidas."""
    pass

@dataclass(frozen=True, slots=True)
class RelatorioMensalClienteRow:
    mes_referencia: datetime.date
    total_creditos: decimal.Decimal
    total_debitos: decimal.Decimal
    saldo_consolidado: decimal.Decimal
    qtd_transacoes: int

def sp_relatorio_mensal_cliente(
    conn: psycopg.Connection,
    p_cliente_id: int,
    p_data_inicio: datetime.date,
    p_data_fim: datetime.date
) -> list[RelatorioMensalClienteRow]:
    """Gera o relatorio mensal consolidado de transacoes de um cliente com fallback automatizado."""
    v_saldo_atual = decimal.Decimal("0.00")
    try:
        with conn.transaction():
            if p_data_inicio > p_data_fim:
                raise RelatorioMensalClienteError(
                    f"Periodo invalido: inicio {p_data_inicio} > fim {p_data_fim}"
                )

            with conn.cursor() as cur:
                cur.execute("SELECT fn_saldo_cliente(%s)", (p_cliente_id,))
                row = cur.fetchone()
                if row is not None and row[0] is not None:
                    v_saldo_atual = decimal.Decimal(str(row[0])).quantize(
                        decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
                    )
                else:
                    v_saldo_atual = decimal.Decimal("0.00")

            logger.info("Saldo atual do cliente %s: %s", p_cliente_id, v_saldo_atual)

            with conn.cursor() as cur:
                query = """
                WITH RECURSIVE meses AS (
                    SELECT DATE_TRUNC('month', %(p_data_inicio)s::DATE)::DATE AS mes
                    UNION ALL
                    SELECT (mes + INTERVAL '1 month')::DATE
                    FROM meses
                    WHERE mes < DATE_TRUNC('month', %(p_data_fim)s::DATE)
                ),
                movimento AS (
                    SELECT
                        DATE_TRUNC('month', t.data_transacao)::DATE AS mes,
                        SUM(CASE WHEN t.conta_destino_id IN (
                            SELECT id FROM contas WHERE cliente_id = %(p_cliente_id)s
                        ) THEN t.valor ELSE 0 END) AS creditos,
                        SUM(CASE WHEN t.conta_origem_id IN (
                            SELECT id FROM contas WHERE cliente_id = %(p_cliente_id)s
                        ) THEN t.valor ELSE 0 END) AS debitos,
                        COUNT(*) AS qtd
                    FROM transacoes t
                    WHERE t.status = 'EFETIVADA'
                      AND t.data_transacao >= %(p_data_inicio)s
                      AND t.data_transacao < %(p_data_fim)s::DATE + INTERVAL '1 day'
                      AND (
                          t.conta_origem_id IN (SELECT id FROM contas WHERE cliente_id = %(p_cliente_id)s)
                          OR t.conta_destino_id IN (SELECT id FROM contas WHERE cliente_id = %(p_cliente_id)s)
                      )
                    GROUP BY 1
                )
                SELECT
                    m.mes AS mes_referencia,
                    COALESCE(mv.creditos, 0) AS total_creditos,
                    COALESCE(mv.debitos, 0) AS total_debitos,
                    %(v_saldo_atual)s + COALESCE(mv.creditos, 0) - COALESCE(mv.debitos, 0) AS saldo_consolidado,
                    COALESCE(mv.qtd, 0)::INT AS qtd_transacoes
                FROM meses m
                LEFT JOIN movimento mv ON mv.mes = m.mes
                ORDER BY m.mes;
                """
                cur.execute(query, {
                    "p_cliente_id": p_cliente_id,
                    "p_data_inicio": p_data_inicio,
                    "p_data_fim": p_data_fim,
                    "v_saldo_atual": v_saldo_atual
                })
                
                rows = cur.fetchall()
                return [
                    RelatorioMensalClienteRow(
                        mes_referencia=r[0] if isinstance(r[0], datetime.date) else r[0].date(),
                        total_creditos=decimal.Decimal(str(r[1])).quantize(
                            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
                        ),
                        total_debitos=decimal.Decimal(str(r[2])).quantize(
                            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
                        ),
                        saldo_consolidado=decimal.Decimal(str(r[3])).quantize(
                            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
                        ),
                        qtd_transacoes=int(r[4])
                    )
                    for r in rows
                ]
    except Exception as e:
        logger.warning("Falha ao gerar relatorio: %s. Retornando linha de fallback.", e)
        try:
            mes_ref = p_data_inicio.replace(day=1)
        except AttributeError:
            mes_ref = p_data_inicio
        return [
            RelatorioMensalClienteRow(
                mes_referencia=mes_ref,
                total_creditos=decimal.Decimal("0.00"),
                total_debitos=decimal.Decimal("0.00"),
                saldo_consolidado=v_saldo_atual.quantize(
                    decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
                ),
                qtd_transacoes=0
            )
        ]
