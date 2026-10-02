from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from idamp.graph.edges import after_bronze_validation, after_gold_validation, after_silver_validation
from idamp.graph.nodes import (
    bronze_hitl_node,
    bronze_load_node,
    bronze_sttm_node,
    bronze_validate_node,
    gold_hitl_node,
    gold_load_node,
    gold_sttm_node,
    gold_validate_node,
    profile_node,
    report_node,
    silver_hitl_node,
    silver_load_node,
    silver_sttm_node,
    silver_validate_node,
)
from idamp.graph.state import PipelineState


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("profile_node", profile_node)
    graph.add_node("bronze_sttm_node", bronze_sttm_node)
    graph.add_node("bronze_hitl_node", bronze_hitl_node)
    graph.add_node("bronze_load_node", bronze_load_node)
    graph.add_node("bronze_validate_node", bronze_validate_node)
    graph.add_node("silver_sttm_node", silver_sttm_node)
    graph.add_node("silver_hitl_node", silver_hitl_node)
    graph.add_node("silver_load_node", silver_load_node)
    graph.add_node("silver_validate_node", silver_validate_node)
    graph.add_node("gold_sttm_node", gold_sttm_node)
    graph.add_node("gold_hitl_node", gold_hitl_node)
    graph.add_node("gold_load_node", gold_load_node)
    graph.add_node("gold_validate_node", gold_validate_node)
    graph.add_node("report_node", report_node)
    graph.add_edge(START, "profile_node")
    graph.add_edge("profile_node", "bronze_sttm_node")
    graph.add_edge("bronze_sttm_node", "bronze_hitl_node")
    graph.add_edge("bronze_hitl_node", "bronze_load_node")
    graph.add_conditional_edges("bronze_load_node", lambda state: "bronze_validate_node" if not state.get("error") else "end", {"bronze_validate_node": "bronze_validate_node", "end": END})
    graph.add_conditional_edges("bronze_validate_node", after_bronze_validation, {"silver_sttm_node": "silver_sttm_node", "bronze_load_node": "bronze_load_node", "end": END})
    graph.add_edge("silver_sttm_node", "silver_hitl_node")
    graph.add_edge("silver_hitl_node", "silver_load_node")
    graph.add_conditional_edges("silver_load_node", lambda state: "silver_validate_node" if not state.get("error") else "end", {"silver_validate_node": "silver_validate_node", "end": END})
    graph.add_conditional_edges("silver_validate_node", after_silver_validation, {"gold_sttm_node": "gold_sttm_node", "silver_load_node": "silver_load_node", "end": END})
    graph.add_edge("gold_sttm_node", "gold_hitl_node")
    graph.add_edge("gold_hitl_node", "gold_load_node")
    graph.add_conditional_edges("gold_load_node", lambda state: "gold_validate_node" if not state.get("error") else "end", {"gold_validate_node": "gold_validate_node", "end": END})
    graph.add_conditional_edges("gold_validate_node", after_gold_validation, {"report_node": "report_node", "gold_load_node": "gold_load_node", "end": END})
    graph.add_edge("report_node", END)
    return graph.compile(checkpointer=MemorySaver(), interrupt_before=["bronze_hitl_node", "silver_hitl_node", "gold_hitl_node"])