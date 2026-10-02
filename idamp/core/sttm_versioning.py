from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from idamp.core.config import settings


def save_sttm(run_id: str, layer: str, entries: list[dict[str, object]]) -> Path:
    settings.ensure_directories()
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()[:10]
    path = settings.sttm_history_dir / f"{run_id[:8]}_{layer}_{digest}.json"
    payload = {"run_id": run_id, "layer": layer, "version": digest, "saved_at": datetime.now(UTC).isoformat(), "mapping": entries}
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path