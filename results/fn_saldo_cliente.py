"""Module for calculating consolidated balance of active accounts for a given client."""

from decimal import Decimal, ROUND_HALF_UP
import psycopg

def fn_saldo_cliente(conn: psycopg.Connection, p_cliente_id: int) -> Decimal:
    """Calculates the total consolidated balance of all active accounts of a client.

    Args:
        conn: Connection to the PostgreSQL database.
        p_cliente_id: The ID of the client.

    Returns:
        The consolidated sum of balances as a Decimal with scale 2.
    """
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(saldo), 0)
                FROM contas
                WHERE cliente_id = %(p_cliente_id)s
                  AND status = 'ATIVA';
                """,
                {"p_cliente_id": p_cliente_id}
            )
            row = cur.fetchone()
            total = row[0] if row and row[0] is not None else Decimal("0.00")
            return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
