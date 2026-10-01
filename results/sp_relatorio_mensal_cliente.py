"""Modulo para geracao de relatorio mensal consolidado de movimentacao de clientes."""

import logging
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from datetime import date
import psycopg

# Configuracao basica de logging
logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class RelatorioMensalClienteRow:
    """Representa uma linha do relatorio mensal do cliente."""
    mes_referencia: date
    total_creditos: Decimal
    total_debitos: Decimal
    saldo_consolidado: Decimal
    qtd_transacoes: int

class RelatorioErro(Exception):
    """Excecao base para erros no relatorio mensal."""
    pass

def sp_relatorio_mensal_cliente(
    conn: psycopg.Connection, 
    p_cliente_id: int, 
    p_data_inicio: date, 
    p_data_fim: date
) -> list[RelatorioMensalClienteRow]:
    """
    Gera um relatorio mensal de movimentacao de um cliente, incluindo creditos, debitos e saldo.
    
    Args:
        conn: Conexao ativa com o banco de dados PostgreSQL.
        p_cliente_id: Identificador unico do cliente.
        p_data_inicio: Data de inicio do periodo do relatorio.
        p_data_fim: Data de fim do periodo do relatorio.

    Returns:
        Lista de objetos RelatorioMensalClienteRow contendo os dados por mes.
    """
    v_saldo_atual: Decimal = Decimal("0.00")
    decimal_precision = Decimal("0.01")

    try:
        # O bloco EXCEPTION do PL/pgSQL cria uma subtransacao (savepoint).
        # No psycopg, transaction() em modo aninhado gerencia o savepoint.
        with conn.transaction():
            # Validacao de periodo
            if p_data_inicio > p_data_fim:
                raise RelatorioErro(f"Periodo invalido: inicio {p_data_inicio} > fim {p_data_fim}")

            # Busca o saldo atual do cliente chamando a funcao do banco
            with conn.cursor() as cur:
                cur.execute("SELECT fn_saldo_cliente(%s)", (p_cliente_id,))
                res_saldo = cur.fetchone()
                if res_saldo and res_saldo[0] is not None:
                    v_saldo_atual = Decimal(res_saldo[0]).quantize(decimal_precision, rounding=ROUND_HALF_UP)

            logger.info("Saldo atual do cliente %s: %s", p_cliente_id, v_saldo_atual)

            # Query principal utilizando CTE recursiva para gerar meses e agregacoes
            sql_principal = """
            WITH RECURSIVE meses AS (
                SELECT DATE_TRUNC('month', %(p_data_inicio)s)::DATE AS mes
                UNION ALL
                SELECT (mes + INTERVAL '1 month')::DATE
                FROM meses
                WHERE mes < DATE_TRUNC('month', %(p_data_fim)s)
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

            params = {
                "p_cliente_id": p_cliente_id,
                "p_data_inicio": p_data_inicio,
                "p_data_fim": p_data_fim,
                "v_saldo_atual": v_saldo_atual
            }

            with conn.cursor() as cur:
                cur.execute(sql_principal, params)
                return [
                    RelatorioMensalClienteRow(
                        mes_referencia=row[0],
                        total_creditos=Decimal(row[1]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                        total_debitos=Decimal(row[2]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                        saldo_consolidado=Decimal(row[3]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                        qtd_transacoes=row[4]
                    ) for row in cur.fetchall()
                ]

    except Exception as e:
        # Handler WHEN OTHERS: o savepoint acima e desfeito antes de entrar aqui.
        logger.warning("Falha ao gerar relatorio: %s. Retornando linha de fallback.", str(e))
        
        # Executa query de fallback conforme comportamento original
        sql_fallback = """
        SELECT
            DATE_TRUNC('month', %(p_data_inicio)s)::DATE,
            0::NUMERIC(18,2),
            0::NUMERIC(18,2),
            COALESCE(%(v_saldo_atual)s, 0),
            0::INT;
        """
        
        with conn.cursor() as cur:
            cur.execute(sql_fallback, {"p_data_inicio": p_data_inicio, "v_saldo_atual": v_saldo_atual})
            row = cur.fetchone()
            if row:
                return [RelatorioMensalClienteRow(
                    mes_referencia=row[0],
                    total_creditos=Decimal(row[1]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                    total_debitos=Decimal(row[2]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                    saldo_consolidado=Decimal(row[3]).quantize(decimal_precision, rounding=ROUND_HALF_UP),
                    qtd_transacoes=row[4]
                )]
            return []
