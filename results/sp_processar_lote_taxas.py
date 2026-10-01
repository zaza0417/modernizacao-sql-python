"""Modulo para processamento de lote de taxas de transacoes bancarias."""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import psycopg

logger = logging.getLogger(__name__)

class ProcessingError(Exception):
    """Excecao lancada durante o processamento de taxas."""
    pass

def sp_processar_lote_taxas(conn: psycopg.Connection, p_data_referencia: date) -> None:
    """
    Calcula e aplica taxas para transacoes efetivadas em uma data de referencia.
    
    Args:
        conn: Conexao ativa com o banco de dados PostgreSQL.
        p_data_referencia: Data das transacoes a serem processadas.
    """
    D2 = Decimal("0.01")
    D4 = Decimal("0.0001")
    
    with conn.transaction():
        # 1. Carregamento previo das taxas vigentes para evitar N+1 queries
        # O uso de DISTINCT ON garante que pegamos a versao mais recente (vigente_de DESC)
        rates = {}
        with conn.cursor() as cur_rates:
            cur_rates.execute("""
                SELECT tipo_operacao, percentual, valor_minimo
                FROM (
                    SELECT tipo_operacao, percentual, valor_minimo,
                           ROW_NUMBER() OVER (PARTITION BY tipo_operacao ORDER BY vigente_de DESC) as rn
                    FROM taxas
                    WHERE vigente_de <= %(ref_date)s
                      AND (vigente_ate IS NULL OR vigente_ate >= %(ref_date)s)
                ) t WHERE rn = 1
            """, {"ref_date": p_data_referencia})
            for row in cur_rates.fetchall():
                rates[row[0]] = {
                    "percentual": row[1].quantize(D4, ROUND_HALF_UP),
                    "valor_minimo": row[2].quantize(D2, ROUND_HALF_UP)
                }

        # 2. Busca das transacoes do lote
        with conn.cursor() as cur_trans:
            cur_trans.execute("""
                SELECT id, conta_origem_id, tipo, valor
                FROM transacoes
                WHERE DATE(data_transacao) = %(ref_date)s
                  AND status = 'EFETIVADA'
                  AND tipo <> 'TARIFA'
            """, {"ref_date": p_data_referencia})
            transactions = cur_trans.fetchall()

        v_total_taxas = Decimal("0.00").quantize(D2, ROUND_HALF_UP)
        v_count = 0

        # 3. Processamento iterativo
        for v_id, v_origem, v_tipo, v_valor in transactions:
            rate_info = rates.get(v_tipo)
            if rate_info is None:
                continue
            
            v_percentual = rate_info["percentual"]
            v_minimo = rate_info["valor_minimo"]
            v_valor_dec = v_valor.quantize(D2, ROUND_HALF_UP)

            # Calculo base: GREATEST(v_valor * v_percentual / 100.0, v_minimo)
            calc_tax = (v_valor_dec * v_percentual / Decimal("100.0")).quantize(D2, ROUND_HALF_UP)
            v_taxa = max(calc_tax, v_minimo)

            # Ajuste por tipo (CASE original)
            if v_tipo == 'TRANSFERENCIA':
                v_taxa = v_taxa
            elif v_tipo == 'SAQUE':
                v_taxa = (v_taxa * Decimal("1.10")).quantize(D2, ROUND_HALF_UP)
            else:
                v_taxa = (v_taxa * Decimal("0.90")).quantize(D2, ROUND_HALF_UP)

            if v_origem is not None:
                with conn.cursor() as write_cur:
                    # Debito na conta origem
                    write_cur.execute(
                        "UPDATE contas SET saldo = saldo - %(taxa)s WHERE id = %(origem)s",
                        {"taxa": v_taxa, "origem": v_origem}
                    )
                    # Registro da nova transacao de tarifa
                    write_cur.execute("""
                        INSERT INTO transacoes (conta_origem_id, tipo, valor, status)
                        VALUES (%(origem)s, 'TARIFA', %(taxa)s, 'EFETIVADA')
                    """, {"origem": v_origem, "taxa": v_taxa})
                    # Log de auditoria individual com JSONB
                    write_cur.execute("""
                        INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes)
                        VALUES (
                            'transacoes', %(tid)s::bigint, 'TARIFA_APLICADA',
                            jsonb_build_object(
                                'transacao_origem', %(tid)s::bigint,
                                'tipo_origem', %(tipo)s::text,
                                'valor_origem', %(valor)s::numeric,
                                'percentual', %(perc)s::numeric,
                                'taxa_aplicada', %(taxa)s::numeric
                            )
                        )
                    """, {
                        "tid": v_id, "tipo": v_tipo, "valor": v_valor_dec,
                        "perc": v_percentual, "taxa": v_taxa
                    })
                
                v_total_taxas = (v_total_taxas + v_taxa).quantize(D2, ROUND_HALF_UP)
                v_count += 1

        # 4. Log final do lote
        with conn.cursor() as summary_cur:
            summary_cur.execute("""
                INSERT INTO log_auditoria (entidade, acao, detalhes)
                VALUES (
                    'lote_taxas', 'LOTE_PROCESSADO',
                    jsonb_build_object(
                        'data_referencia', %(ref_date)s::date,
                        'transacoes', %(count)s::integer,
                        'total_taxas', %(total)s::numeric
                    )
                )
            """, {
                "ref_date": p_data_referencia,
                "count": v_count,
                "total": v_total_taxas
            })
