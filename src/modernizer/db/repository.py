import os
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
