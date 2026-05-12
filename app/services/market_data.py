"""行情数据封装：A股/港股 走 akshare，美股走 yfinance。

所有函数都做了异常吞咽和兜底，避免单个数据源挂掉影响整个页面。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from app.utils.logger import get_logger

logger = get_logger("market")


# ---------- A 股 ----------

def a_stock_hist(symbol: str, start: str | None = None, end: str | None = None,
                 period: str = "daily", adjust: str = "qfq") -> pd.DataFrame:
    """A 股历史 K 线。symbol 形如 '002613' / '600519' / '300750'。"""
    try:
        import akshare as ak
    except Exception as e:
        logger.warning("a_stock_hist: akshare not available: %s", e)
        return pd.DataFrame()

    if start is None:
        start = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")
    if end is None:
        end = datetime.now().strftime("%Y%m%d")

    rename = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg",
    }
    # A 股代码兼容 6 位 / 不带前导 0 等
    raw = symbol.strip().upper().replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
    candidates = [raw, raw.zfill(6)]
    candidates = list(dict.fromkeys(candidates))

    last_err = None
    for sym in candidates:
        try:
            df = ak.stock_zh_a_hist(symbol=sym, period=period,
                                    start_date=start, end_date=end, adjust=adjust)
            if df is None or df.empty:
                logger.info("a_stock_hist(%s): empty for sym=%s", symbol, sym)
                continue
            df = df.rename(columns=rename)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            last_err = e
            logger.info("a_stock_hist(%s) sym=%s failed: %s", symbol, sym, e)
            continue

    logger.warning("a_stock_hist(%s): all formats failed. last_err=%s", symbol, last_err)
    return pd.DataFrame()


# ---------- 港股 ----------

def hk_stock_hist(symbol: str, start: str | None = None, end: str | None = None,
                  adjust: str = "qfq") -> pd.DataFrame:
    """港股历史。symbol 形如 '09992' / '9992' / '00700'。

    akshare 不同版本对港股代码格式要求不同（5 位带前导 0 / 4 位 / 不带前导 0），
    所以我们逐个尝试，第一个能拉到非空数据的就返回。同时对新上市股自动拉长历史窗口。
    """
    try:
        import akshare as ak
    except Exception as e:
        logger.warning("hk_stock_hist: akshare not available: %s", e)
        return pd.DataFrame()

    if start is None:
        # 默认拉 2 年。新股可能上市时间短，无需限定 1 年
        start = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")
    if end is None:
        end = datetime.now().strftime("%Y%m%d")

    rename = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg",
    }

    # 尝试多种代码格式
    raw = symbol.strip().upper().replace("HK", "").replace(".", "")
    candidates: list[str] = [raw]  # 原样兜底
    if raw.isdigit():
        c5 = raw.zfill(5)
        c4 = raw.zfill(4)
        for c in (c5, c4):
            if c not in candidates:
                candidates.append(c)

    last_err = None
    for sym in candidates:
        try:
            df = ak.stock_hk_hist(symbol=sym, period="daily",
                                  start_date=start, end_date=end, adjust=adjust)
            if df is None or df.empty:
                logger.info("hk_stock_hist(%s): empty data for sym=%s", symbol, sym)
                continue
            df = df.rename(columns=rename)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            last_err = e
            logger.info("hk_stock_hist(%s) sym=%s failed: %s", symbol, sym, e)
            continue

    logger.warning("hk_stock_hist(%s): all formats failed (tried %s). last_err=%s",
                   symbol, candidates, last_err)
    return pd.DataFrame()


# ---------- 美股 ----------

def us_stock_hist(symbol: str, period: str = "1y") -> pd.DataFrame:
    """美股历史。symbol 形如 'AAPL'."""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period=period)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index().rename(
            columns={"Date": "date", "Open": "open", "High": "high",
                     "Low": "low", "Close": "close", "Volume": "volume"}
        )
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df["pct_chg"] = df["close"].pct_change() * 100
        return df
    except Exception as e:
        logger.warning("us_stock_hist(%s) failed: %s", symbol, e)
        return pd.DataFrame()


# ---------- 分发 ----------

def stock_hist(symbol: str, market: str, **kwargs) -> pd.DataFrame:
    market = market.lower()
    if market == "a":
        return a_stock_hist(symbol, **kwargs)
    if market == "hk":
        return hk_stock_hist(symbol, **kwargs)
    if market == "us":
        return us_stock_hist(symbol, **kwargs)
    return pd.DataFrame()


# ---------- 板块 ----------

def sector_concept_rank() -> pd.DataFrame:
    """A 股概念板块涨跌幅榜（akshare 提供）。"""
    try:
        import akshare as ak
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.warning("sector_concept_rank failed: %s", e)
        return pd.DataFrame()


def sector_industry_rank() -> pd.DataFrame:
    """A 股行业板块涨跌幅榜。"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.warning("sector_industry_rank failed: %s", e)
        return pd.DataFrame()


# ---------- 港股新股 / 打新 ----------

def hk_ipo_calendar() -> pd.DataFrame:
    """港股新股招股、上市日历。逐个尝试 akshare 现役接口，记录每次结果。"""
    try:
        import akshare as ak
    except Exception as e:
        logger.warning("hk_ipo_calendar: akshare not available: %s", e)
        return pd.DataFrame()

    # akshare 不同版本接口名不同，全部试一遍
    candidates = [
        "stock_hk_new_ipo_em",        # 东方财富
        "stock_hk_ipo_info",          # 新浪
        "stock_hk_new_ipo_eastmoney", # 旧版命名
        "stock_hk_ggt_components_em", # 港股通成分
        "stock_hk_indicator_eniu",    # 备用
    ]
    for fn_name in candidates:
        fn = getattr(ak, fn_name, None)
        if fn is None:
            logger.info("hk_ipo_calendar: %s not in akshare", fn_name)
            continue
        try:
            df = fn()
            if df is not None and not df.empty:
                logger.info("hk_ipo_calendar: got %d rows from %s, cols=%s",
                            len(df), fn_name, list(df.columns)[:10])
                return df
            logger.info("hk_ipo_calendar: %s returned empty", fn_name)
        except Exception as e:
            logger.info("hk_ipo_calendar: %s failed: %s", fn_name, e)
            continue

    logger.warning("hk_ipo_calendar: all akshare endpoints exhausted, returning empty")
    return pd.DataFrame()


# ---------- 新股推荐池 ----------

def yf_quote(symbol: str) -> dict | None:
    """通用 yfinance 行情：返回 {price, pct_24h, volume}。

    适用于 ETF、指数、加密币、个股。失败返回 None。
    """
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="5d")
        if df is None or df.empty or len(df) < 2:
            return None
        last = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        vol = df["Volume"].iloc[-1] if "Volume" in df.columns else 0.0
        return {
            "ticker": symbol,
            "price": float(last),
            "pct_24h": float((last / prev - 1.0) * 100.0),
            "volume": float(vol),
        }
    except Exception as e:
        logger.info("yf_quote(%s) failed: %s", symbol, e)
        return None


def crypto_quote(symbol: str) -> dict | None:
    """加密币行情：symbol 形如 'BTC-USD'，返回 {price, pct_24h, volume}。

    用 yfinance 的现货 ticker，24/7 都有数据。
    """
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(period="5d")
        if df is None or df.empty or len(df) < 2:
            return None
        last = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        vol = df["Volume"].iloc[-1] if "Volume" in df.columns else 0.0
        return {
            "price": float(last),
            "pct_24h": float((last / prev - 1.0) * 100.0),
            "volume": float(vol),
        }
    except Exception as e:
        logger.warning("crypto_quote(%s) failed: %s", symbol, e)
        return None


def a_new_stock_calendar() -> pd.DataFrame:
    """A 股新股申购日历。"""
    try:
        import akshare as ak
        for fn_name in ("stock_zh_a_new", "stock_xgsglb_em", "stock_zh_a_new_em"):
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                df = fn()
                if df is not None and not df.empty:
                    return df
            except Exception:
                continue
        return pd.DataFrame()
    except Exception as e:
        logger.warning("a_new_stock_calendar failed: %s", e)
        return pd.DataFrame()
