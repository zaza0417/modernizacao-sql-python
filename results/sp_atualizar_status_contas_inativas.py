"""Modulo para atualizacao de status de contas inativas."""

import logging
from dataclasses import dataclass
import psycopg

logger = logging.getLogger(__name__)


class ContaInativaError(Exception):
    """Excecao levantada quando ocorre erro na atualizacao de contas inativas."""

    pass


@dataclass(frozen=True, slots=True)
class SpAtualizarStatusContasInativasResult:
    p_afetadas: int


def sp_atualizar_status_contas_inativas(
    conn: psycopg.Connection, p_dias: int
) -> SpAtualizarStatusContasInativasResult:
    """Marca como INATIVA toda conta que nao tenha movimentacao ha mais de p_dias dias."""
    if p_dias is None or p_dias <= 0:
        raise ContaInativaError(f"Parametro p_dias deve ser positivo, recebido: {p_dias}")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE contas c
                SET status = 'INATIVA'
                WHERE c.status = 'ATIVA'
                AND NOT EXISTS (
                    SELECT 1
                    FROM transacoes t
                    WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
                    AND t.data_transacao >= NOW() - (%(dias_str)s::text || ' days')::INTERVAL
                )
                """,
                {"dias_str": str(p_dias)},
            )
            p_afetadas = cur.rowcount

            cur.execute(
                """
                INSERT INTO log_auditoria (entidade, acao, detalhes)
                VALUES (
                    'contas',
                    'INATIVACAO_LOTE',
                    jsonb_build_object('dias', %(dias)s::bigint, 'afetadas', %(afetadas)s::bigint)
                )
                """,
                {"dias": p_dias, "afetadas": p_afetadas},
            )

    return SpAtualizarStatusContasInativasResult(p_afetadas=p_afetadas)
