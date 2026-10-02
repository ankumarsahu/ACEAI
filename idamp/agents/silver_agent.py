from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_integer_dtype, is_numeric_dtype

from idamp.core.config import settings


def _fill_value(transformation: str) -> object:
    if transformation.startswith("FILL:"):
        raw = transformation.partition(":")[2].strip()
        if raw.lower() in {"null", "none", "nan"}:
            return pd.NA
        if raw.lower() in {"true", "false"}:
            return raw.lower() == "true"
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw.strip("'\"")
    return "Unknown"


def _coerce_fill_value(series: pd.Series, value: object) -> object:
    if is_numeric_dtype(series.dtype):
        numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(numeric_value):
            numeric_value = pd.to_numeric(series, errors="coerce").median()
        if pd.isna(numeric_value):
            numeric_value = 0
        return int(numeric_value) if is_integer_dtype(series.dtype) else float(numeric_value)
    if is_datetime64_any_dtype(series.dtype):
        utc = isinstance(series.dtype, pd.DatetimeTZDtype)
        parsed = pd.to_datetime(value, errors="coerce", utc=utc)
        if pd.isna(parsed):
            existing = series.dropna()
            parsed = existing.mode().iloc[0] if not existing.empty else pd.Timestamp("1970-01-01", tz="UTC" if utc else None)
        return parsed
    if is_bool_dtype(series.dtype):
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "false"}:
            return str(value).lower() == "true"
        existing = series.dropna()
        return existing.mode().iloc[0] if not existing.empty else False
    return str(value)


def load_silver(bronze_paths: list[str], mapping: list[dict[str, object]], run_id: str) -> Path:
    settings.ensure_directories()
    frames = [pd.read_parquet(path) for path in bronze_paths]
    combined = pd.concat(frames, ignore_index=True, sort=False)
    dedup_keys = [str(item["target_column"]) for item in mapping if "DEDUP_KEY" in str(item.get("notes", "")).upper()]
    for item in mapping:
        column = str(item.get("target_column", ""))
        if column not in combined.columns:
            continue
        transformation = str(item.get("transformation", ""))
        if transformation.startswith("FILL:") or combined[column].isna().any():
            fill_value = _coerce_fill_value(combined[column], _fill_value(transformation))
            combined[column] = combined[column].fillna(fill_value)
    if dedup_keys:
        existing_keys = [key for key in dedup_keys if key in combined.columns]
        if existing_keys:
            combined = combined.drop_duplicates(subset=existing_keys, keep="last")
    if "pk_silver_id" in combined.columns:
        combined = combined.drop(columns=["pk_silver_id"])
    combined.insert(0, "pk_silver_id", range(1, len(combined) + 1))
    output = settings.silver_dir / f"{run_id}_silver.parquet"
    combined.to_parquet(output, index=False)
    return output