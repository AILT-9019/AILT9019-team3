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
load_dotenv(BASE_DIR / "apikey.env", override=False)

PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model_env": "DEEPSEEK_MODEL",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "qwen": {
        "base_url_env": "QWEN_BASE_URL",
        "model_env": "QWEN_MODEL",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
}


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    timezone: ZoneInfo
    semester_start: date
    semester_end: date
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    extractor_mode: str
    max_upload_mb: int
    max_doc_chars: int
    max_files_per_upload: int
    port: int
    prompt_version: str = "v2"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    timezone_name = os.getenv("TIMEZONE", "Asia/Hong_Kong")
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider not in PROVIDER_DEFAULTS:
        provider = "deepseek"
    profile = PROVIDER_DEFAULTS[provider]
    base_url = os.getenv(profile["base_url_env"], profile["base_url"])
    model = os.getenv(profile["model_env"], profile["model"])
    base_url = os.getenv("LLM_BASE_URL", base_url).rstrip("/")
    model = os.getenv("LLM_MODEL", model)
    return Settings(
        base_dir=BASE_DIR,
        data_dir=data_dir,
        timezone=ZoneInfo(timezone_name),
        semester_start=date.fromisoformat(os.getenv("SEMESTER_START", "2026-08-31")),
        semester_end=date.fromisoformat(os.getenv("SEMESTER_END", "2026-12-06")),
        llm_provider=provider,
        llm_base_url=base_url,
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=model,
        extractor_mode=os.getenv("EXTRACTOR_MODE", "live").strip().lower(),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
        max_doc_chars=int(os.getenv("MAX_DOC_CHARS", "200000")),
        max_files_per_upload=int(os.getenv("MAX_FILES_PER_UPLOAD", "20")),
        port=int(os.getenv("PORT", "32922")),
    )
