"""Módulo contendo a função para consolidar saldo de contas de um cliente."""
from decimal import Decimal, ROUND_HALF_UP
import psycopg

def fn_saldo_cliente(conn: psycopg.Connection, p_cliente_id: int) -> Decimal:
    """
    Retorna o saldo total consolidado de todas as contas ativas de um cliente.

    Args:
        conn: Conexão ativa com o banco de dados PostgreSQL.
        p_cliente_id: Identificador único do cliente.

    Returns:
        Decimal: O saldo consolidado arredondado para duas casas decimais.
    """
    target_scale = Decimal("0.00")
    
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(saldo), 0)
                FROM contas
                WHERE cliente_id = %(cliente_id)s
                  AND status = 'ATIVA';
                """,
                {"cliente_id": p_cliente_id}
            )
            
            row = cur.fetchone()
            raw_value = row[0] if row is not None else Decimal("0")
            
            # Atribuição v_total NUMERIC(18,2) no PL/pgSQL exige o arredondamento imediato
            v_total = Decimal(raw_value).quantize(target_scale, rounding=ROUND_HALF_UP)
            
            return v_total