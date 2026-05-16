"""时区工具：北京时间统一处理。"""
from __future__ import annotations

from datetime import datetime

import pytz

BEIJING = pytz.timezone("Asia/Shanghai")


def now_bj() -> datetime:
    return datetime.now(BEIJING)


def fmt_bj(dt: datetime | None = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        dt = now_bj()
    if dt.tzinfo is None:
        dt = BEIJING.localize(dt)
    return dt.astimezone(BEIJING).strftime(fmt)
