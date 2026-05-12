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
    """A 股历史 K 线。symbol 形如 '002613'."""
    try:
        import akshare as ak
        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=symbol, period=period, start_date=start, end_date=end, adjust=adjust)
        if df is None or df.empty:
            return pd.DataFrame()
        # 列名归一化
        rename = {
            "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
            "最低": "low", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg",
        }
        df = df.rename(columns=rename)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.warning("a_stock_hist(%s) failed: %s", symbol, e)
        return pd.DataFrame()


# ---------- 港股 ----------

def hk_stock_hist(symbol: str, start: str | None = None, end: str | None = None,
                  adjust: str = "qfq") -> pd.DataFrame:
    """港股历史。symbol 形如 '09992'(5位带前导0)."""
    try:
        import akshare as ak
        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        sym = symbol.zfill(5)
        df = ak.stock_hk_hist(symbol=sym, period="daily", start_date=start, end_date=end, adjust=adjust)
        if df is None or df.empty:
            return pd.DataFrame()
        rename = {
            "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
            "最低": "low", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg",
        }
        df = df.rename(columns=rename)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.warning("hk_stock_hist(%s) failed: %s", symbol, e)
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
    """港股新股招股、上市日历。"""
    try:
        import akshare as ak
        # 不同 akshare 版本接口名不同，做容错
        for fn_name in ("stock_hk_new_ipo_em", "stock_hk_ipo_info", "stock_hk_new_ipo_eastmoney"):
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
        logger.warning("hk_ipo_calendar failed: %s", e)
        return pd.DataFrame()


# ---------- 新股推荐池 ----------

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
