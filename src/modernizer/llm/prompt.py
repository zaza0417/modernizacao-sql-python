from modernizer.graph.state import PipelineState

SYSTEM_PROMPT = """\
Voce converte stored procedures PL/pgSQL em modulos Python 3.14 equivalentes.

Regras obrigatorias do codigo gerado:
- Use apenas a biblioteca padrao e psycopg 3.
- A funcao principal tem o mesmo nome da rotina original e recebe
  `conn: psycopg.Connection` como primeiro parametro.
- Mantenha operacoes de dados em SQL parametrizado (%(nome)s). Nunca monte SQL
  com f-string ou concatenacao.
- Controle transacional explicito com `with conn.transaction():`. Um bloco
  EXCEPTION do original equivale a uma transacao aninhada (savepoint).
- NUMERIC vira decimal.Decimal, com a mesma escala do tipo declarado.
- Parametros OUT e resultados com varias colunas viram dataclasses
  (frozen=True, slots=True).
- RAISE EXCEPTION vira uma excecao Python propria do modulo. RAISE NOTICE e
  RAISE WARNING viram chamadas de logging.
- JSONB e enviado com psycopg.types.json.Jsonb.
- Docstring do modulo na primeira linha do arquivo, antes dos imports.
- Type hints em tudo e docstring na funcao principal.
- Importe apenas o que for usado.
- O codigo deve ser completo e executavel, sem trechos omitidos.

Preserve o comportamento observavel da rotina original. Siga as orientacoes de
risco recebidas. Em `decisions`, liste cada decisao de traducao relevante e
qualquer ponto em que o comportamento difere do original, com o motivo.
"""


def build_user_prompt(state: PipelineState) -> str:
    parsed = state["parsed"]
    analysis = state["analysis"]

    parameters = "\n".join(
        f"- {p['name']} ({p['mode']}): {p['type']}" for p in parsed["parameters"]
    ) or "- nenhum"
    variables = "\n".join(
        f"- {v['name']}: {v['type']}" for v in parsed["variables"]
    ) or "- nenhuma"
    constructs = ", ".join(
        f"{name}={count}" for name, count in analysis["constructs"].items()
    )
    risks = "\n".join(
        f"- [{r['severity']}] {r['code']}: {r['guidance']}" for r in analysis["risks"]
    ) or "- nenhum"

    sections = [
        f"## Rotina\n{parsed['kind']} {parsed['name']}\n"
        f"Retorno: {parsed['returns'] or 'nenhum'}",
        f"## Parametros\n{parameters}",
        f"## Variaveis locais\n{variables}",
        f"## Construcoes encontradas\n{constructs}",
        f"## Tabelas referenciadas\n{', '.join(analysis['tables']) or 'nenhuma'}",
        f"## Funcoes do banco chamadas\n"
        f"{', '.join(analysis['function_calls']) or 'nenhuma'}",
        f"## Riscos de traducao e orientacoes\n{risks}",
    ]

    if state.get("schema_ddl"):
        sections.append(f"## Schema das tabelas\n```sql\n{state['schema_ddl']}\n```")

    sections.append(f"## Codigo original\n```sql\n{state['source_code']}\n```")

    previous_errors = (state.get("validation") or {}).get("errors")
    if state.get("generated_code") and previous_errors:
        sections.append(
            "## Tentativa anterior rejeitada pela validacao\n"
            f"```python\n{state['generated_code']}\n```\n"
            "Erros encontrados:\n"
            + "\n".join(f"- {e}" for e in previous_errors)
            + "\nCorrija esses erros e devolva o modulo completo."
        )

    return "\n\n".join(sections)