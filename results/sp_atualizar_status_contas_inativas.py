"""Modulo para atualizacao de status de contas inativas."""
import psycopg
from psycopg.types.json import Jsonb
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class SpError(Exception):
    """Excecao base para a rotina de processamento de contas."""
    pass

@dataclass(frozen=True, slots=True)
class SpAtualizarStatusContasInativasResult:
    """
    Encapsula o resultado da operacao de inativacao em lote.
    
    Attributes:
        p_afetadas (int): Quantidade de registros de contas atualizados.
    """
    p_afetadas: int

def sp_atualizar_status_contas_inativas(conn: psycopg.Connection, p_dias: int) -> SpAtualizarStatusContasInativasResult:
    """
    Marca como INATIVA toda conta que nao tenha movimentacao ha mais de p_dias dias.
    
    Args:
        conn: Conexao ativa com o banco de dados PostgreSQL.
        p_dias: Numero de dias de inatividade para considerar a conta inativa.
        
    Returns:
        SpAtualizarStatusContasInativasResult contendo o numero de linhas afetadas.
        
    Raises:
        SpError: Se o parametro p_dias for nulo ou nao positivo.
    """
    if p_dias is None or p_dias <= 0:
        raise SpError(f"Parametro p_dias deve ser positivo, recebido: {p_dias}")

    with conn.transaction():
        with conn.cursor() as cur:
            # Executa a atualizacao em lote filtrando por ausencia de transacoes no intervalo
            cur.execute("""
                UPDATE contas c
                SET status = 'INATIVA'
                WHERE c.status = 'ATIVA'
                AND NOT EXISTS (
                    SELECT 1
                    FROM transacoes t
                    WHERE (t.conta_origem_id = c.id OR t.conta_destino_id = c.id)
                    AND t.data_transacao >= NOW() - (%(dias)s || ' days')::INTERVAL
                )
            """, {"dias": p_dias})
            
            # Captura o numero de linhas afetadas (GET DIAGNOSTICS ROW_COUNT)
            p_afetadas = cur.rowcount

            # Registro de auditoria com detalhes em formato JSONB
            detalhes = {"dias": p_dias, "afetadas": p_afetadas}
            cur.execute("""
                INSERT INTO log_auditoria (entidade, acao, detalhes)
                VALUES ('contas', 'INATIVACAO_LOTE', %(detalhes)s)
            """, {"detalhes": Jsonb(detalhes)})

            return SpAtualizarStatusContasInativasResult(p_afetadas=p_afetadas)