from modernizer.graph.state import PipelineState


from modernizer.dialects import get_dialect
from modernizer.graph.state import PipelineState


def parse_node(state: PipelineState) -> dict:
    dialect_name = state.get("dialect", "postgres")
    try:
        dialect = get_dialect(dialect_name)
        parsed = dialect.parse(state["source_code"])
    except Exception as exc:
        return {
            "errors": [f"parse: {exc}"],
            "status": "falha",
        }
    return {"parsed": parsed, "dialect": dialect_name}