from langgraph.graph import END, START, StateGraph

from modernizer.graph.state import PipelineState
from modernizer.nodes.analyze import analyze_node
from modernizer.nodes.generate import generate_node
from modernizer.nodes.parse import parse_node
from modernizer.nodes.validate import validate_node

MAX_ATTEMPTS = 3


def _continue_or_stop(next_node: str):
    def route(state: PipelineState) -> str:
        return END if state.get("errors") else next_node

    return route


def _after_validate(state: PipelineState) -> str:
    has_errors = bool(state["validation"]["errors"])
    if has_errors and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate"
    return END


def build_graph():
    builder = StateGraph(PipelineState)

    builder.add_node("parse", parse_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("generate", generate_node)
    builder.add_node("validate", validate_node)

    builder.add_edge(START, "parse")
    builder.add_conditional_edges("parse", _continue_or_stop("analyze"), ["analyze", END])
    builder.add_conditional_edges("analyze", _continue_or_stop("generate"), ["generate", END])
    builder.add_conditional_edges("generate", _continue_or_stop("validate"), ["validate", END])
    builder.add_conditional_edges("validate", _after_validate, ["generate", END])

    return builder.compile()


graph = build_graph()