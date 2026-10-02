from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from idamp.core.config import settings


AGG_PATTERN = re.compile(r"\b(SUM|AVG|COUNT)\s*\(\s*([^)]*)\s*\)", re.IGNORECASE)
GROUP_PATTERN = re.compile(r"\bGROUP\s+BY\s+([\w .,\-]+)", re.IGNORECASE)
FILTER_PATTERN = re.compile(r"\bFILTER\s*:\s*([\w .-]+?)\s*(==|=|>=|<=|>|<)\s*([^;]+)", re.IGNORECASE)
DATE_TRUNC_PATTERN = re.compile(r"DATE_TRUNC\s*\(\s*['\"]month['\"]\s*,\s*(?:PARSE_DATE\s*\(\s*)?([\w]+)", re.IGNORECASE)


def _apply_filter(frame: pd.DataFrame, expression: str) -> pd.DataFrame:
    match = FILTER_PATTERN.search(expression)
    if not match:
        return frame
    column, operator, raw_value = (part.strip() for part in match.groups())
    if column not in frame.columns:
        return frame
    value = raw_value.strip().strip("'\"")
    series = frame[column]
    if operator in {"=", "=="}:
        mask = series.astype(str) == value
    else:
        numeric = pd.to_numeric(series, errors="coerce")
        target = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(target):
            dates = pd.to_datetime(series, errors="coerce", utc=True)
            date_value = pd.to_datetime(value, errors="coerce", utc=True)
            if pd.isna(date_value):
                return frame
            numeric = dates
            target = date_value
        mask = {">": numeric > target, "<": numeric < target, ">=": numeric >= target, "<=": numeric <= target}[operator]
    return frame.loc[mask]


def build_gold(silver_paths: list[str], mapping: list[dict[str, object]], run_id: str, max_rows: int = 8) -> Path:
    settings.ensure_directories()
    frames = [pd.read_parquet(path) for path in silver_paths]
    frame = frames[0]
    for other in frames[1:]:
        shared = [column for column in frame.columns if column in other.columns]
        frame = frame.merge(other, how="outer", on=shared or None, suffixes=("", "_right"))
    entries = mapping[:8]
    for entry in entries:
        frame = _apply_filter(frame, str(entry.get("transformation", "")))
        date_match = DATE_TRUNC_PATTERN.search(str(entry.get("transformation", "")))
        target = str(entry.get("target_column", ""))
        if date_match and date_match.group(1) in frame.columns and target:
            dates = pd.to_datetime(frame[date_match.group(1)], errors="coerce", utc=True)
            frame[target] = dates.dt.tz_convert(None).dt.to_period("M").dt.start_time
    group_columns: list[str] = []
    for entry in entries:
        match = GROUP_PATTERN.search(str(entry.get("transformation", "")))
        if match:
            for candidate in (name.strip() for name in match.group(1).split(",")):
                if candidate in frame.columns and candidate not in group_columns:
                    group_columns.append(candidate)
    aggregations: dict[str, tuple[str, str]] = {}
    for entry in entries:
        transform = str(entry.get("transformation", "DIRECT"))
        match = AGG_PATTERN.search(transform)
        if match:
            operation, source = match.groups()
            source = source.strip()
            if source not in frame.columns and str(entry.get("source_column", "")) in frame.columns:
                source = str(entry["source_column"])
            if source in frame.columns:
                pandas_operation = "mean" if operation.upper() == "AVG" else operation.lower()
                aggregations[str(entry["target_column"])] = (source, pandas_operation)
    if aggregations:
        grouped = frame.groupby(group_columns, dropna=False) if group_columns else None
        if grouped is not None:
            result = grouped.agg(**{name: (source, operation) for name, (source, operation) in aggregations.items()}).reset_index()
        else:
            result = pd.DataFrame({name: [getattr(frame[source], operation)()] for name, (source, operation) in aggregations.items()})
    else:
        result = pd.DataFrame(index=frame.index)
        for entry in entries:
            source = str(entry.get("source_column", ""))
            target = str(entry.get("target_column", ""))
            if source in frame.columns and target:
                result[target] = frame[source]
        if result.empty:
            result = frame.copy()
    if "pk_gold_id" in result.columns:
        result = result.drop(columns=["pk_gold_id"])
    result.insert(0, "pk_gold_id", range(1, len(result) + 1))
    output = settings.gold_dir / f"{run_id}_gold.parquet"
    result.head(max_rows).to_parquet(output, index=False)
    return output