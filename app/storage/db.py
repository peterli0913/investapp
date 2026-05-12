"""SQLite 持久化：缓存抓取结果与用户自选。"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from app.utils.config import settings
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("db")
_LOCK = threading.Lock()


def _ensure_dir() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dir()
    conn = sqlite3.connect(settings.db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = [
    # 通用模块结果缓存（每个模块的最新一次更新）
    """
    CREATE TABLE IF NOT EXISTS module_snapshot (
        module        TEXT NOT NULL,
        key           TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (module, key)
    )
    """,
    # 历史记录（便于回看每天的内容）
    """
    CREATE TABLE IF NOT EXISTS module_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        module       TEXT NOT NULL,
        key          TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )
    """,
    # 用户自选股
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        symbol     TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        market     TEXT NOT NULL,   -- a / hk / us
        added_at   TEXT NOT NULL
    )
    """,
]


def init_db() -> None:
    with _LOCK, get_conn() as conn:
        for sql in SCHEMA:
            conn.execute(sql)
        # 初始三只自选
        seed = [
            ("002613", "胜宏科技", "a"),
            ("02590", "极智嘉", "hk"),
            ("09992", "泡泡马特", "hk"),
        ]
        for sym, name, market in seed:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist(symbol, name, market, added_at) VALUES(?,?,?,?)",
                (sym, name, market, now_bj().isoformat()),
            )
    logger.info("DB initialized at %s", settings.db_path)


# -------- snapshot helpers --------

def save_snapshot(module: str, key: str, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    ts = now_bj().isoformat()
    with _LOCK, get_conn() as conn:
        conn.execute(
            "INSERT INTO module_snapshot(module, key, payload_json, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(module, key) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
            (module, key, text, ts),
        )
        conn.execute(
            "INSERT INTO module_history(module, key, payload_json, updated_at) VALUES(?,?,?,?)",
            (module, key, text, ts),
        )


def load_snapshot(module: str, key: str = "default") -> tuple[Any | None, str | None]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload_json, updated_at FROM module_snapshot WHERE module=? AND key=?",
            (module, key),
        ).fetchone()
    if not row:
        return None, None
    return json.loads(row["payload_json"]), row["updated_at"]


def list_history(module: str, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, payload_json, updated_at FROM module_history "
            "WHERE module=? ORDER BY id DESC LIMIT ?",
            (module, limit),
        ).fetchall()
    out = []
    for r in rows:
        out.append({"key": r["key"], "updated_at": r["updated_at"], "payload": json.loads(r["payload_json"])})
    return out


# -------- watchlist --------

def get_watchlist() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT symbol, name, market, added_at FROM watchlist ORDER BY added_at ASC").fetchall()
    return [dict(r) for r in rows]


def add_watchlist(symbol: str, name: str, market: str) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO watchlist(symbol, name, market, added_at) VALUES(?,?,?,?)",
            (symbol, name, market, now_bj().isoformat()),
        )


def remove_watchlist(symbol: str) -> None:
    with _LOCK, get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol,))
