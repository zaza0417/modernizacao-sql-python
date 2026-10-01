"""Module for transferring funds between accounts with audit logging."""

import logging
from decimal import Decimal, ROUND_HALF_UP
import psycopg

# Configure logging
logger = logging.getLogger(__name__)

# Constant for currency rounding
_CENT = Decimal("0.01")

class TransferenciaError(Exception):
    """Base exception for transfer operation errors."""
    pass

def sp_transferir_entre_contas(
    conn: psycopg.Connection, 
    p_conta_origem: int, 
    p_conta_destino: int, 
    p_valor: Decimal
) -> None:
    """
    Transfers a value between two accounts in an atomic transaction.
    Validates balance, account status, and records the transaction.

    :param conn: Active psycopg connection.
    :param p_conta_origem: ID of the source account.
    :param p_conta_destino: ID of the destination account.
    :param p_valor: Amount to transfer (NUMERIC 18,2).
    :raises TransferenciaError: If validation fails or database error occurs.
    """
    # Initial rounding to match NUMERIC(18,2) behavior
    v_valor = p_valor.quantize(_CENT, rounding=ROUND_HALF_UP) if p_valor is not None else None

    try:
        # The EXCEPTION block in PL/pgSQL creates a sub-transaction (savepoint)
        with conn.transaction():
            # Parameter validation
            if v_valor is None or v_valor <= 0:
                raise TransferenciaError(f"Valor invalido para transferencia: {v_valor}")
            
            if p_conta_origem == p_conta_destino:
                raise TransferenciaError("Conta de origem e destino nao podem ser iguais")

            with conn.cursor() as cur:
                # Select source account with row lock
                cur.execute(
                    "SELECT saldo, status FROM contas WHERE id = %(id)s FOR UPDATE",
                    {"id": p_conta_origem}
                )
                row_origem = cur.fetchone()
                
                if row_origem is None:
                    raise TransferenciaError(f"Conta de origem {p_conta_origem} nao encontrada")
                
                v_saldo_origem, v_status_origem = row_origem
                # Ensure precision from DB
                v_saldo_origem = v_saldo_origem.quantize(_CENT, rounding=ROUND_HALF_UP)

                # Select destination account with row lock
                cur.execute(
                    "SELECT status FROM contas WHERE id = %(id)s FOR UPDATE",
                    {"id": p_conta_destino}
                )
                row_destino = cur.fetchone()
                v_status_destino = row_destino[0] if row_destino else None

                # Status validation
                if v_status_origem != 'ATIVA' or v_status_destino != 'ATIVA':
                    raise TransferenciaError("Ambas as contas precisam estar ATIVAS")

                # Balance validation
                if v_saldo_origem < v_valor:
                    raise TransferenciaError(f"Saldo insuficiente: saldo={v_saldo_origem} valor={v_valor}")

                # Perform updates
                cur.execute(
                    "UPDATE contas SET saldo = saldo - %(valor)s WHERE id = %(id)s",
                    {"valor": v_valor, "id": p_conta_origem}
                )
                cur.execute(
                    "UPDATE contas SET saldo = saldo + %(valor)s WHERE id = %(id)s",
                    {"valor": v_valor, "id": p_conta_destino}
                )

                # Record transaction
                cur.execute(
                    """INSERT INTO transacoes (conta_origem_id, conta_destino_id, tipo, valor) 
                       VALUES (%(origem)s, %(destino)s, 'TRANSFERENCIA', %(valor)s)""",
                    {"origem": p_conta_origem, "destino": p_conta_destino, "valor": v_valor}
                )

                # Success log
                cur.execute(
                    """INSERT INTO log_auditoria (entidade, entidade_id, acao, detalhes) 
                       VALUES ('transacoes', NULL, 'TRANSFERENCIA_OK', 
                       jsonb_build_object('origem', %(o)s::bigint, 'destino', %(d)s::bigint, 'valor', %(v)s::numeric))""",
                    {"o": p_conta_origem, "d": p_conta_destino, "v": v_valor}
                )

    except Exception as e:
        # Handler for OTHERS: Log error in a separate transaction (outside the failed sub-transaction)
        with conn.cursor() as cur_err:
            cur_err.execute(
                """INSERT INTO log_auditoria (entidade, acao, detalhes)
                   VALUES ('transacoes', 'TRANSFERENCIA_ERRO', 
                   jsonb_build_object('origem', %(o)s::bigint, 'destino', %(d)s::bigint, 
                                      'valor', %(v)s::numeric, 'erro', %(err)s::text))""",
                {
                    "o": p_conta_origem, 
                    "d": p_conta_destino, 
                    "v": v_valor, 
                    "err": str(e)
                }
            )
        # Re-raise the exception as per the original PL/pgSQL RAISE statement
        raise