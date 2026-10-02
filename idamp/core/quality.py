from __future__ import annotations

import pandas as pd


def quality_score(frame: pd.DataFrame) -> float:
    if frame.empty or len(frame.columns) == 0:
        return 0.0
    completeness = 1.0 - float(frame.isna().mean().mean())
    return round(max(0.0, min(100.0, completeness * 100.0)), 2)


def validate_sttm(entries: list[dict[str, object]], allowed_sources: set[str]) -> list[str]:
    errors: list[str] = []
    required = {"source_column", "target_column", "transformation", "data_type", "notes"}
    allowed_types = {"str", "int64", "float64", "datetime64"}
    if not entries:
        errors.append("The mapping cannot be empty.")
    targets: list[str] = []
    for index, entry in enumerate(entries):
        missing = required - entry.keys()
        if missing:
            errors.append(f"Row {index + 1}: missing {', '.join(sorted(missing))}.")
        source = str(entry.get("source_column", ""))
        target = str(entry.get("target_column", "")).strip()
        if source and source not in allowed_sources and source not in {"_load_timestamp", "_source_file"}:
            errors.append(f"Row {index + 1}: source column '{source}' is not available.")
        if not target:
            errors.append(f"Row {index + 1}: target column is required.")
        elif target in targets:
            errors.append(f"Row {index + 1}: target column '{target}' is duplicated.")
        else:
            targets.append(target)
        if entry.get("data_type") not in allowed_types:
            errors.append(f"Row {index + 1}: choose a supported data type.")
    return errors