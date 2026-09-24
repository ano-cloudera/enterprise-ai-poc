from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.graph.nodes import (
    analyze_result,
    direct_chat,
    execute_sql,
    fallback,
    forecast,
    generate_sql,
    input_guard,
    metric_unavailable,
    normalize_intent,
    output_guard,
    repair_sql,
    resolve_semantics,
    result_checker,
    route_intent,
    ui_action_generator,
    validate_sql,
    visualization_planner,
    weather,
    market,
)
from app.ossie.graph_nodes import ossie_analytical, ossie_conversational
from app.graph.state import GraphState


def _after_guard(state: GraphState) -> str:
    return "fallback" if state.get("guardrail_error") else "route_intent"


def _after_intent(state: GraphState) -> str:
    return {
        "analytical": "resolve_semantics",
        "forecast": "forecast",
        "weather": "weather",
        "market": "market",
        "conversational": "direct_chat",
        "ossie_analytical": "ossie_analytical",
        "ossie_conversational": "ossie_conversational",
        "blocked": "fallback",
    }.get(state.get("intent", ""), "fallback")


def _after_validation(state: GraphState) -> str:
    if state.get("validation_status") == "passed":
        return "execute_sql"
    attempts = state.get("repair_attempts", 0)
    return "repair_sql" if attempts < get_settings().sql_max_repair_attempts else "fallback"


def _after_result_check(state: GraphState) -> str:
    return "analyze_result" if state.get("result_check_status") == "OK" else "fallback"


def _after_semantics(state: GraphState) -> str:
    return "metric_unavailable" if state.get("intent") == "metric_unavailable" else "normalize_intent"


def build_graph():
    """Controlled deterministic graph. No autonomous tool loop and no database write path."""
    graph = StateGraph(GraphState)
    for name, node in {
        "input_guard": input_guard,
        "route_intent": route_intent,
        "resolve_semantics": resolve_semantics,
        "metric_unavailable": metric_unavailable,
        "normalize_intent": normalize_intent,
        "generate_sql": generate_sql,
        "repair_sql": repair_sql,
        "validate_sql": validate_sql,
        "execute_sql": execute_sql,
        "result_checker": result_checker,
        "analyze_result": analyze_result,
        "visualization_planner": visualization_planner,
        "ui_action_generator": ui_action_generator,
        "output_guard": output_guard,
        "direct_chat": direct_chat,
        "forecast": forecast,
        "weather": weather,
        "market": market,
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
            "resolve_semantics": "resolve_semantics",
            "forecast": "forecast",
            "weather": "weather",
            "market": "market",
            "direct_chat": "direct_chat",
            "ossie_analytical": "ossie_analytical",
            "ossie_conversational": "ossie_conversational",
            "fallback": "fallback",
        },
    )
    graph.add_conditional_edges("resolve_semantics", _after_semantics, {"metric_unavailable": "metric_unavailable", "normalize_intent": "normalize_intent"})
    graph.add_edge("normalize_intent", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges("validate_sql", _after_validation, {"execute_sql": "execute_sql", "repair_sql": "repair_sql", "fallback": "fallback"})
    graph.add_edge("repair_sql", "validate_sql")
    graph.add_edge("execute_sql", "result_checker")
    graph.add_conditional_edges("result_checker", _after_result_check, {"analyze_result": "analyze_result", "fallback": "fallback"})
    graph.add_edge("analyze_result", "visualization_planner")
    graph.add_edge("visualization_planner", "ui_action_generator")
    graph.add_edge("ui_action_generator", "output_guard")
    graph.add_edge("output_guard", END)
    graph.add_edge("direct_chat", "output_guard")
    graph.add_edge("forecast", "output_guard")
    graph.add_edge("weather", "output_guard")
    graph.add_edge("market", "output_guard")
    graph.add_edge("ossie_analytical", "output_guard")
    graph.add_edge("ossie_conversational", "output_guard")
    graph.add_edge("metric_unavailable", "output_guard")
    graph.add_edge("fallback", END)
    return graph.compile()


workflow = build_graph()
