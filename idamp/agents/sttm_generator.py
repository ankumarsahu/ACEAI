from __future__ import annotations

import ast
import json
from typing import Any

from idamp.core.retry import chat_text, parse_json_array


def _normalize(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for entry in entries:
        normalized.append(
            {
                "source_column": _canonical_source_column(entry.get("source_column", "")),
                "target_column": str(entry.get("target_column", "")),
                "transformation": str(entry.get("transformation", "DIRECT")),
                "data_type": _canonical_data_type(entry.get("data_type", "str")),
                "notes": str(entry.get("notes", "")),
            }
        )
    return normalized


def _canonical_source_column(value: object) -> str:
    parsed = value
    if isinstance(value, str) and value.lstrip().startswith(("[", "(")):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed = value
    if isinstance(parsed, (list, tuple)):
        parsed = next((item for item in parsed if isinstance(item, str) and item.strip()), "")
    return str(parsed).strip() if parsed is not None else ""


def _canonical_data_type(value: object) -> str:
    normalized = str(value).strip().lower().replace("_", "")
    if normalized in {"int64", "int", "integer", "long", "int32", "int16", "int8"}:
        return "int64"
    if normalized in {"float64", "float", "double", "decimal", "number", "numeric"}:
        return "float64"
    if any(token in normalized for token in ("datetime", "timestamp", "date", "time")):
        return "datetime64"
    return "str"


def generate_sttm(layer: str, intent: str, profile: dict[str, Any], hint: str = "") -> list[dict[str, object]]:
    if layer == "bronze":
        columns = profile.get("columns", {})
        rules = "Include every available source column and preserve it; use DIRECT or CAST."
    elif layer == "silver":
        columns = profile.get("silver_columns", profile.get("columns", {}))
        rules = "Include available columns, use DIRECT or FILL:<value>; put DEDUP_KEY in notes for deduplication keys."
    else:
        columns = profile.get("silver_columns", profile.get("columns", {}))
        rules = "Return at most 8 intent-relevant output columns. Use SUM(column), AVG(column), COUNT(column), GROUP BY column, FILTER: column >= value, or DIRECT."
    prompt = (
        f"Business intent: {intent}\nLayer: {layer}\nColumn profile: {json.dumps(columns, default=str)}\n"
        f"User refinement: {hint or 'none'}\n{rules}\n"
        'Return only a JSON array. Every item must contain source_column, target_column, transformation, '
        'data_type (str, int64, float64, datetime64), and notes.'
    )
    raw = chat_text("You design precise source-to-target mappings for auditable data pipelines. Return valid JSON only.", prompt)
    result = _normalize(parse_json_array(raw))
    if layer == "gold":
        result = result[:8]
    return result