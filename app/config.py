from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    timezone: ZoneInfo
    semester_start: date
    semester_end: date
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    extractor_mode: str
    max_upload_mb: int
    max_doc_chars: int
    max_files_per_upload: int
    prompt_version: str = "v1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    timezone_name = os.getenv("TIMEZONE", "Asia/Hong_Kong")
    return Settings(
        base_dir=BASE_DIR,
        data_dir=data_dir,
        timezone=ZoneInfo(timezone_name),
        semester_start=date.fromisoformat(os.getenv("SEMESTER_START", "2026-08-31")),
        semester_end=date.fromisoformat(os.getenv("SEMESTER_END", "2026-12-06")),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        extractor_mode=os.getenv("EXTRACTOR_MODE", "live").strip().lower(),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
        max_doc_chars=int(os.getenv("MAX_DOC_CHARS", "200000")),
        max_files_per_upload=int(os.getenv("MAX_FILES_PER_UPLOAD", "20")),
    )
