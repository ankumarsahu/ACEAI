from __future__ import annotations

from idamp.graph.state import PipelineState


def _retry_or_fail(state: PipelineState, layer: str, load_node: str) -> str:
    if state.get("retry_counts", {}).get(layer, 0) >= 3:
        return "end"
    return load_node


def after_bronze_validation(state: PipelineState) -> str:
    if state.get("error"):
        return "end"
    if state.get("bronze_validation", {}).get("valid"):
        return "silver_sttm_node"
    return _retry_or_fail(state, "bronze", "bronze_load_node")


def after_silver_validation(state: PipelineState) -> str:
    if state.get("error"):
        return "end"
    if state.get("silver_validation", {}).get("valid"):
        return "gold_sttm_node"
    return _retry_or_fail(state, "silver", "silver_load_node")


def after_gold_validation(state: PipelineState) -> str:
    if state.get("error"):
        return "end"
    if state.get("gold_validation", {}).get("valid"):
        return "report_node"
    return _retry_or_fail(state, "gold", "gold_load_node")