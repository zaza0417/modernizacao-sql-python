import sqlglot
from pglast import parse_plpgsql
from sqlglot import exp

from modernizer.dialects.base import Parameter, ParsedProcedure, Variable


class PostgresDialect:
    name = "postgres"

    def parse(self, source: str) -> ParsedProcedure:
        tree = sqlglot.parse_one(source, read="postgres")
        if not isinstance(tree, exp.Create):
            raise ValueError("Esperado CREATE FUNCTION ou CREATE PROCEDURE")

        udf = tree.this                     # UserDefinedFunction
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
            mode = "IN"                     # sem modo explícito = IN
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