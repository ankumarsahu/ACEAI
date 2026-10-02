from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from idamp.core.config import settings


def profile_files(file_infos: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    profiles: dict[str, Any] = {"files": {}, "columns": {}}
    all_frames: list[pd.DataFrame] = []
    for info in file_infos:
        path = Path(str(info["path"]))
        frame = pd.read_csv(path, low_memory=False)
        all_frames.append(frame)
        columns: dict[str, Any] = {}
        for column in frame.columns:
            series = frame[column]
            columns[str(column)] = {
                "dtype": str(series.dtype),
                "null_percent": round(float(series.isna().mean() * 100), 2),
                "unique_count": int(series.nunique(dropna=True)),
                "top_values": series.dropna().astype(str).value_counts().head(5).to_dict(),
            }
        profiles["files"][path.name] = {"rows": len(frame), "columns": columns}
    combined = pd.concat(all_frames, ignore_index=True, sort=False) if all_frames else pd.DataFrame()
    for column in combined.columns:
        series = combined[column]
        profiles["columns"][str(column)] = {
            "dtype": str(series.dtype),
            "null_percent": round(float(series.isna().mean() * 100), 2),
            "unique_count": int(series.nunique(dropna=True)),
            "top_values": series.dropna().astype(str).value_counts().head(5).to_dict(),
        }
    output = settings.landing_dir / f"{run_id}_combined_profile.json"
    output.write_text(json.dumps(profiles, indent=2, default=str), encoding="utf-8")
    return profiles