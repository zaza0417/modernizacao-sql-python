from modernizer.dialects import get_dialect
from modernizer.graph.state import PipelineState


def analyze_node(state: PipelineState) -> dict:
    try:
        dialect = get_dialect(state.get("dialect", "postgres"))
        analysis = dialect.analyze(state["parsed"])
    except Exception as exc:
        return {"errors": [f"analyze: {exc}"], "status": "falha"}
    return {"analysis": analysis}
