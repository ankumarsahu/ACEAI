from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Callable

from langgraph.types import interrupt

from idamp.agents.auditor import ensure_run, record_stage
from idamp.agents.bronze_agent import load_bronze
from idamp.agents.gold_agent import build_gold
from idamp.agents.profiler import profile_files
from idamp.agents.reporter import create_report
from idamp.agents.silver_agent import load_silver
from idamp.agents.sttm_generator import generate_sttm
from idamp.agents.validator import validate
from idamp.core.sttm_versioning import save_sttm
from idamp.graph.state import PipelineState


def _stage(state: PipelineState, name: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = datetime.now(UTC).isoformat()
    run_id = state["run_id"]
    try:
        update = operation()
        validation = next((value for key, value in update.items() if key.endswith("_validation")), {})
        record_stage(run_id, name, "completed", rows_out=validation.get("rows"), quality=validation.get("quality_score"), started_at=started)
        return update
    except Exception as exc:
        record_stage(run_id, name, "failed", error=str(exc), started_at=started)
        return {"error": f"{name}: {exc}", "current_step": "error"}


def profile_node(state: PipelineState) -> dict[str, Any]:
    ensure_run(state["run_id"], state["business_intent"])
    return _stage(state, "profile", lambda: {"profile": profile_files(state["uploaded_files_info"], state["run_id"]), "current_step": "bronze_sttm"})


def _sttm_node(state: PipelineState, layer: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        profile = dict(state["profile"])
        if layer == "silver":
            profile["silver_columns"] = {column: {} for column in _silver_column_names(state)}
        mapping = generate_sttm(layer, state["business_intent"], profile, state.get("sttm_hint", ""))
        save_sttm(state["run_id"], layer, mapping)
        return {f"{layer}_sttm": mapping, "current_step": f"{layer}_hitl", "sttm_hint": ""}
    return _stage(state, f"{layer}_sttm", work)


def _silver_column_names(state: PipelineState) -> list[str]:
    names = {str(entry["target_column"]) for entry in state.get("bronze_sttm", [])}
    names.update({"_load_timestamp", "_source_file"})
    return sorted(names)


def bronze_sttm_node(state: PipelineState) -> dict[str, Any]:
    return _sttm_node(state, "bronze")


def silver_sttm_node(state: PipelineState) -> dict[str, Any]:
    return _sttm_node(state, "silver")


def gold_sttm_node(state: PipelineState) -> dict[str, Any]:
    return _sttm_node(state, "gold")


def _hitl_node(state: PipelineState, layer: str) -> dict[str, Any]:
    if state.get("approved_stage") != layer:
        interrupt({"stage": layer, "message": "Review and approve the source-to-target mapping."})
    return {"approved_stage": "", "current_step": f"{layer}_load"}


def bronze_hitl_node(state: PipelineState) -> dict[str, Any]:
    return _hitl_node(state, "bronze")


def silver_hitl_node(state: PipelineState) -> dict[str, Any]:
    return _hitl_node(state, "silver")


def gold_hitl_node(state: PipelineState) -> dict[str, Any]:
    return _hitl_node(state, "gold")


def bronze_load_node(state: PipelineState) -> dict[str, Any]:
    return _stage(state, "bronze_load", lambda: {"bronze_paths": [str(path) for path in load_bronze(state["uploaded_files_info"], state["bronze_sttm"], state["run_id"])], "current_step": "bronze_validate"})


def bronze_validate_node(state: PipelineState) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        outcome = validate("bronze", state["bronze_paths"], state.get("uploaded_column_count", 0))
        retries = dict(state.get("retry_counts", {}))
        if not outcome["valid"]:
            retries["bronze"] = retries.get("bronze", 0) + 1
        return {"bronze_validation": outcome, "retry_counts": retries, "current_step": "bronze_validate", "error": "Bronze validation exhausted retries." if retries.get("bronze", 0) > 2 else ""}
    return _stage(state, "bronze_validate", work)


def silver_load_node(state: PipelineState) -> dict[str, Any]:
    return _stage(state, "silver_load", lambda: {"silver_paths": [str(load_silver(state["bronze_paths"], state["silver_sttm"], state["run_id"]))], "current_step": "silver_validate"})


def silver_validate_node(state: PipelineState) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        outcome = validate("silver", state["silver_paths"])
        retries = dict(state.get("retry_counts", {}))
        if not outcome["valid"]:
            retries["silver"] = retries.get("silver", 0) + 1
        return {"silver_validation": outcome, "retry_counts": retries, "current_step": "silver_validate", "error": "Silver validation exhausted retries." if retries.get("silver", 0) > 2 else ""}
    return _stage(state, "silver_validate", work)


def gold_load_node(state: PipelineState) -> dict[str, Any]:
    return _stage(state, "gold_load", lambda: {"gold_paths": [str(build_gold(state["silver_paths"], state["gold_sttm"], state["run_id"], state.get("max_gold_rows", 8)))], "current_step": "gold_validate"})


def gold_validate_node(state: PipelineState) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        outcome = validate("gold", state["gold_paths"])
        retries = dict(state.get("retry_counts", {}))
        if not outcome["valid"]:
            retries["gold"] = retries.get("gold", 0) + 1
        return {"gold_validation": outcome, "retry_counts": retries, "current_step": "gold_validate", "error": "Gold validation exhausted retries." if retries.get("gold", 0) > 2 else ""}
    return _stage(state, "gold_validate", work)


def report_node(state: PipelineState) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        path, sql, result = create_report(state["business_intent"], state["gold_paths"][0], state["run_id"])
        result_payload = {
            "columns": [str(column) for column in result.columns],
            "records": json.loads(result.to_json(orient="records", date_format="iso")),
        }
        return {"report_path": str(path), "report_sql": sql, "report_result_df": result_payload, "current_step": "complete"}
    return _stage(state, "report", work)