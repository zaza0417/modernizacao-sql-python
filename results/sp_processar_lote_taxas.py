"""Modulo para processar lote de taxas de transacoes bancarias de uma data especifica."""

from decimal import Decimal, ROUND_HALF_UP
import datetime
import logging
import psycopg

logger = logging.getLogger(__name__)

DEC_2 = Decimal("0.01")
DEC_4 = Decimal("0.0001")

class ProcessamentoTaxasError(Exception):
    """Excecao lancada para erros no processamento do lote de taxas."""
    pass

def sp_processar_lote_taxas(conn: psycopg.Connection, p_data_referencia: datetime.date) -> None:
    """Processa transacoes de uma determinada data, aplicando e registrando as respectivas taxas."""
    with conn.transaction():
        # 1. Busca as taxas vigentes na data para evitar buscas individuais (N+1)
        query_taxas = """
            SELECT DISTINCT ON (tipo_operacao) tipo_operacao, percentual, valor_minimo
            FROM taxas
            WHERE vigente_de <= %(data_ref)s
              AND (vigente_ate IS NULL OR vigente_ate >= %(data_ref)s)
            ORDER BY tipo_operacao, vigente_de DESC;
        """
        taxas_map = {}
        with conn.cursor() as cur:
            cur.execute(query_taxas, {"data_ref": p_data_referencia})
            for row in cur.fetchall():
                tipo, perc, min_val = row
                taxas_map[tipo] = {
                    "percentual": Decimal(perc).quantize(DEC_4, rounding=ROUND_HALF_UP) if perc is not None else None,
                    "valor_minimo": Decimal(min_val).quantize(DEC_2, rounding=ROUND_HALF_UP) if min_val is not None else None
                }

        # 2. Busca as transacoes elegiveis
        query_transacoes = """
            SELECT id, conta_origem_id, tipo, valor
            FROM transacoes
            WHERE DATE(data_transacao) = %(data_ref)s
              AND status = 'EFETIVADA'
              AND tipo <> 'TARIFA';
        """
        
        v_total_taxas = Decimal("0.00").quantize(DEC_2, rounding=ROUND_HALF_UP)
        v_count = 0

        with conn.cursor() as cur:
            cur.execute(query_transacoes, {"data_ref": p_data_referencia})
            transacoes = cur.fetchall()

            for v_id, v_origem, v_tipo, v_valor_raw in transacoes:
                v_valor = Decimal(v_valor_raw).quantize(DEC_2, rounding=ROUND_HALF_UP)
                taxa_info = taxas_map.get(v_tipo)
                
                if not taxa_info or taxa_info["percentual"] is None:
                    continue

                v_percentual = taxa_info["percentual"]
                v_minimo = taxa_info["valor_minimo"]

                # Calcula a taxa base: GREATEST(v_valor * v_percentual / 100.0, v_minimo)
                calc_val = (v_valor * v_percentual / Decimal("100.0")).quantize(DEC_2, rounding=ROUND_HALF_UP)
                v_taxa = max(calc_val, v_minimo)

                # Aplica as multiplicacoes do CASE
                if v_tipo == "TRANSFERENCIA":
                    v_taxa = v_taxa
                elif v_tipo == "SAQUE":
                    v_taxa = (v_taxa * Decimal("1.10")).quantize(DEC_2, rounding=ROUND_HALF_UP)
                else:
                    v_taxa = (v_taxa * Decimal("0.90")).quantize(DEC_2, rounding=ROUND_HALF_UP)

                if v_origem is not None:
                    # Reduz o saldo da conta de origem
                    cur.execute(
                        "UPDATE contas SET saldo = saldo - %(taxa)s WHERE id = %(id)s",
                        {"taxa": v_taxa, "id": v_origem}
                    )

                    # Registra a nova transacao de TARIFA
                    cur.execute(
                        """
                        INSERT INTO transacoes (conta_origem_id, tipo, valor, status)
                        VALUES (%(origem)s, 'TARIFA', %(taxa)s, 'EFETIVADA')
                        """,
                        {"origem": v_origem, "taxa": v_taxa}
                    )

                    # Registra a auditoria da transacao processada
                    cur.execute(
                        """
                        INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
                        VALUES (
                            'transacoes',
                            %(v_id)s::bigint,
                            'TARIFA_APLICADA',
                            jsonb_build_object(
                                'transacao_origem', %(v_id)s::bigint,
                                'tipo_origem', %(v_tipo)s::text,
                                'valor_origem', %(v_valor)s::numeric,
                                'percentual', %(v_percentual)s::numeric,
                                'taxa_aplicada', %(v_taxa)s::numeric
                            )
                        )
                        """,
                        {
                            "v_id": v_id,
                            "v_tipo": v_tipo,
                            "v_valor": v_valor,
                            "v_percentual": v_percentual,
                            "v_taxa": v_taxa
                        }
                    )

                    v_total_taxas = (v_total_taxas + v_taxa).quantize(DEC_2, rounding=ROUND_HALF_UP)
                    v_count += 1

            # Log final de encerramento do lote
            cur.execute(
                """
                INSERT INTO log_auditoria (entidade, acao, detalhes)
                VALUES (
                    'lote_taxas',
                    'LOTE_PROCESSADO',
                    jsonb_build_object(
                        'data_referencia', %(p_data_referencia)s::date,
                        'transacoes', %(v_count)s::integer,
                        'total_taxas', %(v_total_taxas)s::numeric
                    )
                )
                """,
                {
                    "p_data_referencia": p_data_referencia,
                    "v_count": v_count,
                    "v_total_taxas": v_total_taxas
                }
            )
