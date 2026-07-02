"""
Assemble the agent as a LangGraph StateGraph.

Topology:

    understand ──(conditional route on intent)──▶ one action node ──▶ END

The graph is compiled once at import and reused for every request. Keeping the
routing in a single conditional edge makes the control flow easy to read and
easy to extend — adding a new capability is a new node plus one route entry.
"""
from __future__ import annotations

import functools

from langgraph.graph import END, StateGraph

from . import nodes
from .state import AgentState

_ACTION_NODES = {
    "check_availability": nodes.node_check_availability,
    "create_reservation": nodes.node_create_reservation,
    "cancel_reservation": nodes.node_cancel_reservation,
    "list_vehicles": nodes.node_list_vehicles,
    "list_reservations": nodes.node_list_reservations,
    "register_vehicle": nodes.node_register_vehicle,
    "smalltalk": nodes.node_smalltalk,
    "fallback": nodes.node_fallback,
}


@functools.lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(AgentState)

    g.add_node("understand", nodes.node_understand)
    for name, fn in _ACTION_NODES.items():
        g.add_node(name, fn)

    g.set_entry_point("understand")
    g.add_conditional_edges(
        "understand",
        nodes.route,
        {name: name for name in _ACTION_NODES},
    )
    for name in _ACTION_NODES:
        g.add_edge(name, END)

    return g.compile()


def run_agent(message: str) -> dict:
    """Execute the full pipeline for one user message and return final state."""
    graph = build_graph()
    final = graph.invoke({"message": message, "trace": []})
    return {
        "reply": final.get("reply", ""),
        "intent": final.get("intent", "unknown"),
        "entities": final.get("entities", {}),
        "nlu_source": final.get("nlu_source", "rules"),
        "result": final.get("result", {}),
        "trace": final.get("trace", []),
    }
