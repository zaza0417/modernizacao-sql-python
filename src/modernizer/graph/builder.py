from langgraph.graph import END, START, StateGraph

from modernizer.graph.state import PipelineState
from modernizer.nodes.analyze import analyze_node
from modernizer.nodes.generate import generate_node
from modernizer.nodes.parse import parse_node
from modernizer.nodes.validate import validate_node
from modernizer.nodes.persist import persist_node

MAX_ATTEMPTS = 3


def _continue_or_stop(next_node: str):
    def route(state: PipelineState) -> str:
        return "persist" if state.get("errors") else next_node

    return route


def _after_validate(state: PipelineState) -> str:
    has_errors = bool(state["validation"]["errors"])
    if has_errors and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "generate"
    return "persist"


def build_graph():
    builder = StateGraph(PipelineState)

    builder.add_node("parse", parse_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("generate", generate_node)
    builder.add_node("validate", validate_node)
    builder.add_node("persist", persist_node)

    builder.add_edge(START, "parse")
    builder.add_conditional_edges("parse", _continue_or_stop("analyze"), ["analyze", "persist"])
    builder.add_conditional_edges("analyze", _continue_or_stop("generate"), ["generate", "persist"])
    builder.add_conditional_edges("generate", _continue_or_stop("validate"), ["validate", "persist"])
    builder.add_conditional_edges("validate", _after_validate, ["generate", "persist"])
    builder.add_edge("persist", END)

    return builder.compile()


graph = build_graph()