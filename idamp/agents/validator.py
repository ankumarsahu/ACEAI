from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from idamp.core.quality import quality_score


def validate(layer: str, paths: list[str], source_column_count: int = 0) -> dict[str, Any]:
    frames = [pd.read_parquet(path) for path in paths]
    frame = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    score = quality_score(frame)
    checks: list[dict[str, Any]] = []
    if layer == "bronze":
        audit_present = {"_load_timestamp", "_source_file"}.issubset(frame.columns)
        checks = [
            {"name": "Rows available", "valid": len(frame) > 0, "detail": f"{len(frame):,} rows"},
            {"name": "Audit columns", "valid": audit_present, "detail": "Load timestamp and source file"},
            {"name": "Source columns preserved", "valid": len(frame.columns) >= source_column_count, "detail": f"{len(frame.columns)} output columns"},
        ]
    elif layer == "silver":
        pk_valid = "pk_silver_id" in frame.columns and frame["pk_silver_id"].notna().all()
        checks = [
            {"name": "Surrogate key", "valid": bool(pk_valid), "detail": "pk_silver_id is present and complete"},
            {"name": "Average quality", "valid": score >= 70, "detail": f"{score:.1f}% completeness"},
        ]
    else:
        has_numeric = any(pd.api.types.is_numeric_dtype(frame[column]) for column in frame.columns)
        checks = [
            {"name": "Rows available", "valid": len(frame) > 0, "detail": f"{len(frame):,} rows"},
            {"name": "Surrogate key", "valid": "pk_gold_id" in frame.columns, "detail": "pk_gold_id present"},
            {"name": "Numeric measure", "valid": has_numeric, "detail": "At least one numeric column"},
        ]
    return {"valid": all(item["valid"] for item in checks), "checks": checks, "rows": len(frame), "quality_score": score}