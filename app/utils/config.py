"""统一配置加载（环境变量 + .env）。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").strip()
    # 兼容旧字段：OPENAI_MODEL 仍可用，但推荐分级配置 fast/deep
    openai_model: str = os.getenv("OPENAI_MODEL", "deepseek-v4-flash").strip()
    openai_model_fast: str = os.getenv(
        "OPENAI_MODEL_FAST",
        os.getenv("OPENAI_MODEL", "deepseek-v4-flash"),
    ).strip()
    openai_model_deep: str = os.getenv(
        "OPENAI_MODEL_DEEP",
        os.getenv("OPENAI_MODEL", "deepseek-v4-pro"),
    ).strip()

    daily_update_hhmm: str = os.getenv("DAILY_UPDATE_HHMM", "06:30").strip()
    timezone: str = os.getenv("TIMEZONE", "Asia/Shanghai").strip()

    db_path: str = os.getenv("DB_PATH", str(ROOT / "app" / "storage" / "stocks.db")).strip()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
