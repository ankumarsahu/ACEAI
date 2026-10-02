from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from idamp.core.config import settings


def _cast(series: pd.Series, data_type: str) -> pd.Series:
    if data_type == "int64":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    if data_type == "float64":
        return pd.to_numeric(series, errors="coerce").astype("Float64")
    if data_type == "datetime64":
        return pd.to_datetime(series, errors="coerce", utc=True)
    return series.astype("string")


def load_bronze(file_infos: list[dict[str, Any]], mapping: list[dict[str, object]], run_id: str) -> list[Path]:
    settings.ensure_directories()
    rename_map = {str(item["source_column"]): str(item["target_column"]) for item in mapping}
    type_map = {str(item["target_column"]): str(item["data_type"]) for item in mapping}
    output_paths: list[Path] = []
    for info in file_infos:
        source_path = Path(str(info["path"]))
        frame = pd.read_csv(source_path, low_memory=False)
        original_count = len(frame.columns)
        mapped = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
        for column, data_type in type_map.items():
            if column in mapped.columns:
                mapped[column] = _cast(mapped[column], data_type)
        mapped["_load_timestamp"] = datetime.now(UTC).isoformat()
        mapped["_source_file"] = source_path.name
        mapped.attrs["source_column_count"] = original_count
        target_path = settings.bronze_dir / f"{run_id}_{source_path.stem}.parquet"
        mapped.to_parquet(target_path, index=False)
        output_paths.append(target_path)
    return output_paths