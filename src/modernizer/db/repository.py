import os
import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

_INSERT = """
    INSERT INTO modernization_history (source_code, generated_code, report, status)
    VALUES (%(source_code)s, %(generated_code)s, %(report)s, %(status)s)
    RETURNING id
"""


def save_execution(
    source_code: str,
    generated_code: str | None,
    report: dict[str, Any],
    status: str,
) -> str:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            _INSERT,
            {
                "source_code": source_code,
                "generated_code": generated_code,
                "report": Jsonb(report),
                "status": status,
            },
        ).fetchone()
    return str(row[0])


_LATEST_SUCCESS = """
    SELECT DISTINCT ON (report->'parsing'->>'name')
           id, report->'parsing'->>'name', source_code, generated_code
      FROM modernization_history
     WHERE status = 'sucesso'
     ORDER BY report->'parsing'->>'name', created_at DESC
"""

_INSERT_EVALUATION = """
    INSERT INTO evaluation_results
        (run_id, execution_id, routine, scenario, equivalent, outcome_match, state_match, details)
    VALUES
        (%(run_id)s, %(execution_id)s, %(routine)s, %(scenario)s, %(equivalent)s,
         %(outcome_match)s, %(state_match)s, %(details)s)
"""


def latest_successful_executions() -> list[dict[str, Any]]:
    """Devolve a execucao bem-sucedida mais recente de cada rotina."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(_LATEST_SUCCESS).fetchall()
    return [
        {"id": str(row[0]), "routine": row[1], "source_code": row[2], "generated_code": row[3]}
        for row in rows
    ]


def save_evaluation(results: list[dict[str, Any]]) -> str:
    """Grava os cenarios de uma rodada de avaliacao e devolve o id da rodada."""
    run_id = str(uuid.uuid4())
    rows = [
        {
            "run_id": run_id,
            "execution_id": r["execution_id"],
            "routine": r["routine"],
            "scenario": r["scenario"],
            "equivalent": r["equivalent"],
            "outcome_match": r["outcome_match"],
            "state_match": r["state_match"],
            "details": Jsonb(
                {
                    "args": r["args"],
                    "original_error": r["original_error"],
                    "generated_error": r["generated_error"],
                }
            ),
        }
        for r in results
    ]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.executemany(_INSERT_EVALUATION, rows)
    return run_id
