"""调度器：每日北京时间 06:30 自动刷新全部 5 个模块。

应用启动时调用 `start_scheduler()` 一次即可（已做单例保护，多次调用安全）。
"""
from __future__ import annotations

import threading
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.modules.ipo import build_ipo_report
from app.modules.recommendations import build_recommendation_report
from app.modules.sectors import build_sector_report
from app.modules.taco import build_taco_report
from app.modules.tracked_stocks import build_tracked_report
from app.utils.config import settings
from app.utils.logger import get_logger
from app.utils.tz import BEIJING

logger = get_logger("scheduler")

_LOCK = threading.Lock()
_SCHEDULER: BackgroundScheduler | None = None


JOBS: dict[str, Callable[[], dict]] = {
    "sectors": build_sector_report,
    "taco": build_taco_report,
    "tracked": build_tracked_report,
    "ipo": build_ipo_report,
    "recommendations": build_recommendation_report,
}


def _run_all() -> None:
    for name, fn in JOBS.items():
        try:
            logger.info("scheduler: running %s", name)
            fn()
        except Exception as e:
            logger.exception("scheduler: %s failed: %s", name, e)


def run_module(name: str) -> dict | None:
    """手动触发某个模块。"""
    fn = JOBS.get(name)
    if not fn:
        return None
    return fn()


def run_all_manual() -> None:
    """手动一键刷新全部。"""
    _run_all()


def start_scheduler() -> BackgroundScheduler:
    global _SCHEDULER
    with _LOCK:
        if _SCHEDULER and _SCHEDULER.running:
            return _SCHEDULER
        sched = BackgroundScheduler(timezone=BEIJING)
        try:
            hh, mm = (int(x) for x in settings.daily_update_hhmm.split(":"))
        except Exception:
            hh, mm = 6, 30
        sched.add_job(
            _run_all,
            CronTrigger(hour=hh, minute=mm, timezone=BEIJING),
            id="daily_refresh",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )
        sched.start()
        _SCHEDULER = sched
        logger.info("scheduler started: daily %02d:%02d %s", hh, mm, BEIJING)
        return sched


def get_next_run() -> str:
    if _SCHEDULER is None:
        return "未启动"
    job = _SCHEDULER.get_job("daily_refresh")
    if not job or not job.next_run_time:
        return "未排程"
    return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
