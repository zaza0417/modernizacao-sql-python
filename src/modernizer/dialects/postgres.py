from collections import Counter

import sqlglot
from pglast import parse_plpgsql
from sqlglot import exp

from modernizer.dialects.base import Analysis, Parameter, ParsedProcedure, Risk, Variable


class PostgresDialect:
    name = "postgres"

    def parse(self, source: str) -> ParsedProcedure:
        tree = sqlglot.parse_one(source, read="postgres")
        if not isinstance(tree, exp.Create):
            raise ValueError("Esperado CREATE FUNCTION ou CREATE PROCEDURE")

        udf = tree.this  # UserDefinedFunction
        props = tree.args.get("properties")
        prop_list = props.expressions if props else []

        function = parse_plpgsql(source)[0]["PLpgSQL_function"]

        return {
            "name": udf.this.name,
            "kind": tree.args["kind"],
            "language": self._language(prop_list),
            "parameters": [self._parameter(c) for c in udf.expressions],
            "returns": self._returns(prop_list),
            "variables": self._variables(function["datums"]),
            "body_source": tree.expression.this,
            "body_tree": function["action"],
        }

    @staticmethod
    def _parameter(col: exp.ColumnDef) -> Parameter:
        io = col.find(exp.InOutColumnConstraint)
        if io is None:
            mode = "IN"  # sem modo explícito = IN
        elif io.args.get("input_") and io.args.get("output"):
            mode = "INOUT"
        elif io.args.get("output"):
            mode = "OUT"
        else:
            mode = "IN"
        return {
            "name": col.name,
            "mode": mode,
            "type": col.args["kind"].sql(dialect="postgres"),
        }

    @staticmethod
    def _returns(prop_list: list[exp.Expression]) -> str | None:
        for p in prop_list:
            if isinstance(p, exp.ReturnsProperty):
                return p.this.sql(dialect="postgres")
        return None

    @staticmethod
    def _language(prop_list: list[exp.Expression]) -> str | None:
        for p in prop_list:
            if isinstance(p, exp.LanguageProperty):
                return p.this.name
        return None

    @staticmethod
    def _variables(datums: list[dict]) -> list[Variable]:
        variables: list[Variable] = []
        for d in datums:
            var = d.get("PLpgSQL_var")
            if var is None or "lineno" not in var:
                continue
            name = var["refname"]
            if name in ("sqlstate", "sqlerrm") or name.startswith("__"):
                continue
            variables.append(
                {
                    "name": name,
                    "type": var["datatype"]["PLpgSQL_type"]["typname"],
                }
            )
        return variables

    def analyze(self, parsed: ParsedProcedure) -> Analysis:
        constructs: Counter[str] = Counter()
        queries: list[str] = []
        self._walk(parsed["body_tree"], constructs, queries)
        tables, functions = self._references(queries)
        return {
            "constructs": dict(constructs),
            "tables": tables,
            "function_calls": functions,
            "risks": self._risks(parsed, constructs, queries, functions),
        }

    def _walk(self, node, constructs: Counter[str], queries: list[str]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("PLpgSQL_stmt_") or key == "PLpgSQL_exception_block":
                    name = key.removeprefix("PLpgSQL_").removeprefix("stmt_")
                    constructs[name] += 1
                if key == "PLpgSQL_expr":
                    queries.append(value["query"])
                self._walk(value, constructs, queries)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, constructs, queries)

    @staticmethod
    def _references(queries: list[str]) -> tuple[list[str], list[str]]:
        tables: set[str] = set()
        functions: set[str] = set()
        for query in queries:
            expr = query.split(":=", 1)[1] if ":=" in query else query
            for candidate in (expr, f"SELECT {expr}"):
                try:
                    tree = sqlglot.parse_one(candidate, read="postgres")
                except Exception:
                    continue
                ctes = {c.alias for c in tree.find_all(exp.CTE)}
                tables.update(
                    t.name for t in tree.find_all(exp.Table) if t.name and t.name not in ctes
                )
                functions.update(
                    f.name
                    for f in tree.find_all(exp.Anonymous)
                    if not f.name.lower().startswith(("json_", "jsonb_"))
                )
                break
        return sorted(tables), sorted(functions)

    @staticmethod
    def _risks(
        parsed: ParsedProcedure,
        constructs: Counter[str],
        queries: list[str],
        functions: list[str],
    ) -> list[Risk]:
        sql_text = " ".join(queries).upper()
        declared = parsed["parameters"] + parsed["variables"]
        types = " ".join(d["type"] for d in declared).upper()
        types += " " + (parsed["returns"] or "").upper()
        writes = sum(q.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries)

        rules = [
            (
                constructs["fetch"] > 0,
                "CURSOR_LOOP",
                "alta",
                "Cursor percorrido linha a linha gera N+1 queries. Prefira uma "
                "operacao set-based ou carga em lote, preservando a semantica."
                " Nao execute consultas dentro do laco: carregue os dados de "
                "apoio em uma unica query antes dele.",
            ),
            (
                constructs["exception_block"] > 0,
                "EXCEPTION_BLOCK",
                "alta",
                "Bloco EXCEPTION cria uma subtransacao: o que o bloco fez e "
                "desfeito antes do handler. Escritas no handler seguidas de RAISE "
                "tambem sao desfeitas pela transacao externa. Todo RAISE EXCEPTION "
                "dentro do bloco, inclusive validacoes de parametros, e capturado "
                "pelo handler WHEN OTHERS: coloque essas validacoes dentro do try."
                " O corpo do bloco fica dentro de um `with conn.transaction()` "
                "aninhado proprio, com o try/except por fora dele, para que o "
                "handler consiga usar a conexao depois de um erro de banco.",
            ),
            (
                "FOR UPDATE" in sql_text,
                "ROW_LOCK",
                "alta",
                "SELECT ... FOR UPDATE bloqueia linhas. Leitura e escrita precisam "
                "ocorrer na mesma transacao e na mesma conexao.",
            ),
            (
                writes >= 2,
                "MULTI_WRITE",
                "alta",
                "Multiplas escritas devem ficar em uma unica transacao atomica.",
            ),
            (
                any(p["mode"] != "IN" for p in parsed["parameters"]),
                "OUT_PARAMS",
                "media",
                "Parametros OUT nao existem em Python: devolva-os no retorno (dataclass).",
            ),
            (
                constructs["return_query"] > 0,
                "SET_RETURNING",
                "media",
                "RETURN QUERY devolve varias linhas: retorne uma lista de dataclasses.",
            ),
            (
                "WITH RECURSIVE" in sql_text,
                "RECURSIVE_CTE",
                "media",
                "CTE recursiva: mantenha em SQL em vez de reescrever com loop Python.",
            ),
            (
                bool(functions),
                "NESTED_CALL",
                "media",
                f"Chama outras funcoes do banco: {', '.join(functions)}. Trate "
                "como dependencia explicita.",
            ),
            (
                "NUMERIC" in types or "DECIMAL" in types,
                "DECIMAL",
                "media",
                "Valores NUMERIC devem usar decimal.Decimal, nunca float. Cada "
                "atribuicao a uma variavel NUMERIC(p,s) arredonda na hora: aplique "
                "quantize com ROUND_HALF_UP a cada atribuicao, nao apenas no final.",
            ),
            (
                constructs["raise"] > 0,
                "RAISE",
                "media",
                "RAISE EXCEPTION vira excecao Python; NOTICE e WARNING viram logging.",
            ),
            (
                constructs["getdiag"] > 0,
                "ROW_COUNT",
                "baixa",
                "GET DIAGNOSTICS ROW_COUNT equivale a cursor.rowcount.",
            ),
            (
                "JSONB" in sql_text,
                "JSONB",
                "baixa",
                "JSONB: mantenha jsonb_build_object no SQL e passe os valores como "
                "parametros com cast explicito em cada um (%(x)s::bigint, "
                "::numeric, ::text, ::date), pois o banco nao infere o tipo de "
                "parametros nessa funcao. Nao use Jsonb() com Decimal nem converta "
                "para str ou float.",
            ),
        ]
        return [
            {"code": code, "severity": severity, "guidance": guidance}
            for condition, code, severity, guidance in rules
            if condition
        ]
