from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    root: Path = PROJECT_ROOT
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    audit_db: Path = PROJECT_ROOT / "audit" / "audit.db"
    landing_dir: Path = PROJECT_ROOT / "data" / "landing"
    bronze_dir: Path = PROJECT_ROOT / "data" / "bronze_layer"
    silver_dir: Path = PROJECT_ROOT / "data" / "silver_layer"
    gold_dir: Path = PROJECT_ROOT / "data" / "gold_layer"
    reports_dir: Path = PROJECT_ROOT / "reports"
    sttm_history_dir: Path = PROJECT_ROOT / "sttm_history"

    def ensure_directories(self) -> None:
        for directory in (
            self.audit_db.parent,
            self.landing_dir,
            self.bronze_dir,
            self.silver_dir,
            self.gold_dir,
            self.reports_dir,
            self.sttm_history_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()