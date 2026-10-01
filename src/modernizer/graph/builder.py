from langgraph.graph import END, START, StateGraph

from modernizer.graph.state import PipelineState
from modernizer.nodes.analyze import analyze_node
from modernizer.nodes.generate import generate_node
from modernizer.nodes.parse import parse_node
from modernizer.nodes.validate import validate_node


def build_graph():
    builder = StateGraph(PipelineState)

    builder.add_node("parse", parse_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("generate", generate_node)
    builder.add_node("validate", validate_node)

    builder.add_edge(START, "parse")
    builder.add_edge("parse", "analyze")
    builder.add_edge("analyze", "generate")
    builder.add_edge("generate", "validate")
    builder.add_edge("validate", END)

    return builder.compile()

graph = build_graph()