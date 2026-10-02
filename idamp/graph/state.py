from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    run_id: str
    business_intent: str
    uploaded_files_info: list[dict[str, Any]]
    profile: dict[str, Any]
    bronze_sttm: list[dict[str, object]]
    silver_sttm: list[dict[str, object]]
    gold_sttm: list[dict[str, object]]
    bronze_paths: list[str]
    silver_paths: list[str]
    gold_paths: list[str]
    bronze_validation: dict[str, Any]
    silver_validation: dict[str, Any]
    gold_validation: dict[str, Any]
    report_path: str
    report_sql: str
    report_result_df: dict[str, Any]
    current_step: str
    sttm_hint: str
    error: str
    approved_stage: str
    retry_counts: dict[str, int]
    max_gold_rows: int
    strict_validation: bool
    uploaded_column_count: int