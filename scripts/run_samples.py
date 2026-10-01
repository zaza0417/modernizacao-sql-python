"""Envia os Anexos B a F para POST /modernize e salva os resultados em results/."""

import json
import sys
import urllib.request
from pathlib import Path

API_URL = "http://127.0.0.1:2024/modernize"
SAMPLES = Path("samples")
RESULTS = Path("results")
PROCEDURES = [
    "fn_saldo_cliente",
    "sp_atualizar_status_contas_inativas",
    "sp_transferir_entre_contas",
    "sp_processar_lote_taxas",
    "sp_relatorio_mensal_cliente",
]


def modernize(source_code: str, schema_ddl: str) -> dict:
    payload = json.dumps(
        {"source_code": source_code, "schema_ddl": schema_ddl}
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    schema = (SAMPLES / "banco_legado.sql").read_text(encoding="utf-8")

    for name in sys.argv[1:] or PROCEDURES:
        source = (SAMPLES / f"{name}.sql").read_text(encoding="utf-8")
        result = modernize(source, schema)

        if result["status"] == "falha":
            print(f"{name}: falha - {result['report']['errors']}")
            continue
        if result["generated_code"]:
            (RESULTS / f"{name}.py").write_text(
                result["generated_code"], encoding="utf-8"
            )
        report = {"id": result["id"], "status": result["status"], **result["report"]}
        (RESULTS / f"{name}.report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{name}: {result['status']} ({result['report']['attempts']} tentativa(s))")


if __name__ == "__main__":
    main()