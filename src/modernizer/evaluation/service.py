"""Calcula a metrica de equivalencia sobre a ultima geracao bem-sucedida de cada rotina."""

import os
from pathlib import Path
from typing import Any

import psycopg

from modernizer.db.repository import latest_successful_executions, save_evaluation
from modernizer.dialects import get_dialect
from modernizer.evaluation.equivalence import compare
from modernizer.evaluation.scenarios import build_scenarios


def run_evaluation() -> dict[str, Any]:
    seed_file = Path(os.getenv("TEST_SEED_FILE", "samples/seed_teste.sql"))
    seed = seed_file.read_text(encoding="utf-8")
    dialect = get_dialect("postgres")
    scenarios = build_scenarios()
    results: list[dict[str, Any]] = []

    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        for execution in latest_successful_executions():
            parsed = dialect.parse(execution["source_code"])
            for scenario in (s for s in scenarios if s.routine == execution["routine"]):
                try:
                    outcome = compare(
                        conn, seed, parsed, execution["generated_code"], scenario.args
                    )
                except Exception as exc:
                    outcome = {
                        "equivalent": False,
                        "outcome_match": False,
                        "state_match": False,
                        "original_error": None,
                        "generated_error": f"falha ao carregar o modulo: {exc}",
                    }
                results.append(
                    {
                        "execution_id": execution["id"],
                        "routine": scenario.routine,
                        "scenario": scenario.label,
                        "args": [str(a) for a in scenario.args],
                        **outcome,
                    }
                )

    run_id = save_evaluation(results)
    return {"run_id": run_id, **summarize(results), "scenarios": results}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_routine: dict[str, dict[str, Any]] = {}
    for result in results:
        entry = by_routine.setdefault(result["routine"], {"total": 0, "equivalent": 0})
        entry["total"] += 1
        entry["equivalent"] += int(result["equivalent"])
    for entry in by_routine.values():
        entry["rate"] = round(entry["equivalent"] / entry["total"], 4)

    total = len(results)
    equivalent = sum(int(r["equivalent"]) for r in results)
    return {
        "total": total,
        "equivalent": equivalent,
        "equivalence_rate": round(equivalent / total, 4) if total else 0.0,
        "by_routine": by_routine,
    }
