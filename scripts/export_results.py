"""Exporta para results/ a execucao bem-sucedida mais recente de cada rotina."""

import json
import os
from pathlib import Path

import psycopg

RESULTS = Path("results")
QUERY = """
    SELECT DISTINCT ON (report->'parsing'->>'name')
           report->'parsing'->>'name', id, status, generated_code, report
      FROM modernization_history
     WHERE status = 'sucesso'
     ORDER BY report->'parsing'->>'name', created_at DESC
"""


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for name, execution_id, status, code, report in conn.execute(QUERY):
            (RESULTS / f"{name}.py").write_text(code, encoding="utf-8")
            full = {"id": str(execution_id), "status": status, **report}
            (RESULTS / f"{name}.report.json").write_text(
                json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"{name}: exportado ({execution_id})")


if __name__ == "__main__":
    main()