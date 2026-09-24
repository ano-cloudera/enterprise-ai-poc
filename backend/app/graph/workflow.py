from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    fallback,
    input_guard,
    output_guard,
    route_intent,
)
from app.ossie.graph_nodes import ossie_analytical, ossie_conversational
from app.graph.state import GraphState

# forecast/weather/market (app.graph.nodes) are deliberately NOT imported or
# wired here: they query DuckDB-synthetic tables directly and haven't been
# retargeted to Impala, so with data_backend defaulting to "impala" they'd
# fail if reachable. Their code stays intact for a future decision (see
# PROJECT_STATE.md) - only routing to them is disconnected.


def _after_guard(state: GraphState) -> str:
    return "fallback" if state.get("guardrail_error") else "route_intent"


def _after_intent(state: GraphState) -> str:
    return {
        "ossie_analytical": "ossie_analytical",
        "ossie_conversational": "ossie_conversational",
        "blocked": "fallback",
    }.get(state.get("intent", ""), "fallback")


def build_graph():
    """Controlled deterministic graph. No autonomous tool loop and no database write path."""
    graph = StateGraph(GraphState)
    for name, node in {
        "input_guard": input_guard,
        "route_intent": route_intent,
        "output_guard": output_guard,
        "ossie_analytical": ossie_analytical,
        "ossie_conversational": ossie_conversational,
        "fallback": fallback,
    }.items():
        graph.add_node(name, node)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges("input_guard", _after_guard, {"route_intent": "route_intent", "fallback": "fallback"})
    graph.add_conditional_edges(
        "route_intent",
        _after_intent,
        {
            "ossie_analytical": "ossie_analytical",
            "ossie_conversational": "ossie_conversational",
            "fallback": "fallback",
        },
    )
    graph.add_edge("ossie_analytical", "output_guard")
    graph.add_edge("ossie_conversational", "output_guard")
    graph.add_edge("output_guard", END)
    graph.add_edge("fallback", END)
    return graph.compile()


workflow = build_graph()
