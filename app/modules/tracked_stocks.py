"""模块 3：热门股票追踪。

初始三只：胜宏科技(002613.SZ)、极智嘉(02590.HK)、泡泡玛特(09992.HK)。
用户可在 UI 上添加/删除。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd

from app.backtest.engine import _signal_ensemble
from app.services.llm_client import llm
from app.services.market_data import stock_hist
from app.services.news_feed import fetch_keywords
from app.services.sentiment import headlines_sentiment
from app.storage.db import get_watchlist, save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("tracked")


def _ma_signal(df: pd.DataFrame) -> str:
    if df.empty or "close" not in df.columns or len(df) < 30:
        return "数据不足"
    s = df["close"].astype(float)
    ma5 = s.rolling(5).mean().iloc[-1]
    ma20 = s.rolling(20).mean().iloc[-1]
    last = s.iloc[-1]
    parts = []
    parts.append("MA5↑" if last > ma5 else "MA5↓")
    parts.append("MA20↑" if last > ma20 else "MA20↓")
    parts.append("金叉" if ma5 > ma20 else "死叉")
    return " / ".join(parts)


def _recent_pct(df: pd.DataFrame, window: int = 20) -> float:
    if df.empty or len(df) < window:
        return 0.0
    s = df["close"].astype(float)
    return float((s.iloc[-1] / s.iloc[-window] - 1.0) * 100.0)


def _news_lang(market: str) -> tuple[str, str]:
    if market == "us":
        return "en-US", "US"
    if market == "hk":
        return "zh-HK", "HK"
    return "zh-CN", "CN"


def _fmt_volume(v: float) -> str:
    """成交量 / 成交额格式化，便于普通人阅读。"""
    if v is None or v != v:
        return "—"
    v = float(v)
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f} 亿"
    if abs(v) >= 1e4:
        return f"{v/1e4:.2f} 万"
    return f"{v:.0f}"


def _today_metrics(df) -> dict:
    """从历史 df 抽出『今日』和『昨日』的关键指标。

    A 股 / 港股的 df 一般包含 amount（成交额）；美股的 yfinance 没有 amount。
    """
    if df is None or df.empty:
        return {}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    last_close = float(last.get("close", 0)) if "close" in last else 0.0
    last_open = float(last.get("open", last_close)) if "open" in last else last_close
    last_high = float(last.get("high", last_close)) if "high" in last else last_close
    last_low = float(last.get("low", last_close)) if "low" in last else last_close
    last_volume = float(last.get("volume", 0)) if "volume" in last else 0.0
    last_amount = float(last.get("amount", 0)) if "amount" in last and last["amount"] == last["amount"] else None

    today_pct = None
    if prev is not None and "close" in prev:
        prev_close = float(prev.get("close", 0))
        if prev_close:
            today_pct = (last_close / prev_close - 1.0) * 100.0

    return {
        "last_date": last["date"].strftime("%Y-%m-%d") if hasattr(last["date"], "strftime") else str(last["date"]),
        "last_close": last_close,
        "last_open": last_open,
        "last_high": last_high,
        "last_low": last_low,
        "today_pct": today_pct,
        "volume": last_volume,
        "volume_str": _fmt_volume(last_volume),
        "amount": last_amount,
        "amount_str": _fmt_volume(last_amount) if last_amount is not None else "—",
    }


def _process_one_stock(w: dict) -> dict:
    sym, name, market = w["symbol"], w["name"], w["market"]
    df = stock_hist(sym, market)
    pct = _recent_pct(df)
    signal = _ma_signal(df)
    metrics = _today_metrics(df)
    lang, country = _news_lang(market)
    news = fetch_keywords([name, f"{name} 股价"], lang=lang, country=country, per=5)
    titles = [n.title for n in news if n.title]
    sentiment = headlines_sentiment(titles)
    ens_signal = _signal_ensemble(df, sentiment=sentiment) if not df.empty else 0
    ens_text = {1: "看多", -1: "看空", 0: "中性"}[ens_signal]
    outlook = llm.stock_outlook(name, pct, titles,
                                f"{signal} · 多因子ensemble:{ens_text} · 情绪:{sentiment:+.2f}")
    outlook["ensemble_signal"] = ens_text
    outlook["sentiment"] = sentiment

    kline = []
    if not df.empty:
        tail = df.tail(120)
        for _, row in tail.iterrows():
            kline.append({
                "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)) if "volume" in row else 0.0,
            })

    return {
        "symbol": sym,
        "name": name,
        "market": market,
        "recent_pct_20d": pct,
        "ma_signal": signal,
        "sentiment": sentiment,
        "ensemble_signal": ens_text,
        "outlook": outlook,
        "metrics": metrics,
        "news": [n.to_dict() for n in news[:10]],
        "kline": kline,
    }


def build_tracked_report() -> dict[str, Any]:
    wl = get_watchlist()
    items: list[dict] = []
    if not wl:
        report = {"updated_at": now_bj().isoformat(), "items": []}
        save_snapshot("tracked", "default", report)
        return report

    with ThreadPoolExecutor(max_workers=min(8, len(wl)), thread_name_prefix="track") as pool:
        futures = [pool.submit(_process_one_stock, w) for w in wl]
        for fut in as_completed(futures):
            try:
                items.append(fut.result())
            except Exception as e:
                logger.warning("tracked stock task failed: %s", e)

    # 保持自选股原顺序
    order = {w["symbol"]: i for i, w in enumerate(wl)}
    items.sort(key=lambda x: order.get(x["symbol"], 999))

    report = {"updated_at": now_bj().isoformat(), "items": items}
    save_snapshot("tracked", "default", report)
    return report
