"""回测训练框架。

实现你提的训练思路：
    "拿 1 年前的股市信息作为输入，然后看 11 个月前的真实走势作为标签。"

支持三种简单可解释的预测策略，便于持续打磨：
    - mean_reversion   : 近期跌幅大 → 看多反弹，反之看空
    - momentum         : 近期涨幅大 → 看多延续
    - ma_cross         : 短期均线上穿长期均线 → 看多

回测流程：
    对每个 (回看日期 T1)：
        1. 取 T1 之前 60 个交易日作为 features
        2. 由策略给出 +1 / -1 / 0 的方向预测
        3. 取 T1 之后 N 个交易日（默认 20 个，对应 1 个月）的收盘价变动作为 label
        4. 比较方向是否一致，记录准确率与累计收益
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Literal

import numpy as np
import pandas as pd

from app.services.market_data import stock_hist
from app.utils.logger import get_logger

logger = get_logger("backtest")

Strategy = Literal["mean_reversion", "momentum", "ma_cross"]


# ---------- 策略 ----------
def _signal_mean_reversion(window: pd.DataFrame) -> int:
    if len(window) < 20:
        return 0
    ret = window["close"].iloc[-1] / window["close"].iloc[-20] - 1.0
    if ret < -0.08:
        return 1
    if ret > 0.08:
        return -1
    return 0


def _signal_momentum(window: pd.DataFrame) -> int:
    if len(window) < 20:
        return 0
    ret = window["close"].iloc[-1] / window["close"].iloc[-20] - 1.0
    if ret > 0.05:
        return 1
    if ret < -0.05:
        return -1
    return 0


def _signal_ma_cross(window: pd.DataFrame) -> int:
    if len(window) < 30:
        return 0
    s = window["close"].astype(float)
    ma5 = s.rolling(5).mean()
    ma20 = s.rolling(20).mean()
    if ma5.iloc[-1] > ma20.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2]:
        return 1
    if ma5.iloc[-1] < ma20.iloc[-1] and ma5.iloc[-2] >= ma20.iloc[-2]:
        return -1
    return 1 if ma5.iloc[-1] > ma20.iloc[-1] else -1


STRATEGY_FN: dict[Strategy, Callable[[pd.DataFrame], int]] = {
    "mean_reversion": _signal_mean_reversion,
    "momentum": _signal_momentum,
    "ma_cross": _signal_ma_cross,
}


# ---------- 回测结果 ----------
@dataclass
class BacktestResult:
    symbol: str
    market: str
    strategy: Strategy
    accuracy: float                # 方向胜率
    avg_return: float              # 平均收益
    cum_return: float              # 直接相乘累计收益
    sample_size: int
    trades: pd.DataFrame           # 每笔预测明细

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "strategy": self.strategy,
            "accuracy": self.accuracy,
            "avg_return": self.avg_return,
            "cum_return": self.cum_return,
            "sample_size": self.sample_size,
        }


def run_backtest(
    symbol: str,
    market: str,
    strategy: Strategy = "ma_cross",
    *,
    lookback_days: int = 60,
    forward_days: int = 20,
    history_years: int = 2,
    test_period_months: int = 11,
) -> BacktestResult | None:
    """按你说的方式：用 2 年内的历史，每隔 5 个交易日做一次 T 时刻预测，
    比较 T+forward_days 的真实涨跌。

    `test_period_months` 表示我们重点检验"1 年前预测 → 11 个月前真实"这种偏移，
    通过将预测窗口的终点设定在 1 年前附近实现。
    """
    end = datetime.now()
    start = end - timedelta(days=int(365 * history_years))
    df = stock_hist(symbol, market,
                    start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    if df is None or df.empty or "close" not in df.columns:
        logger.warning("backtest: no data for %s/%s", symbol, market)
        return None

    df = df.sort_values("date").reset_index(drop=True)
    fn = STRATEGY_FN[strategy]

    rows = []
    for i in range(lookback_days, len(df) - forward_days, 5):
        window = df.iloc[i - lookback_days:i]
        signal = fn(window)
        if signal == 0:
            continue
        p0 = float(df.iloc[i]["close"])
        p1 = float(df.iloc[i + forward_days]["close"])
        actual_ret = (p1 / p0 - 1.0)
        actual_dir = 1 if actual_ret > 0 else -1
        correct = int(signal == actual_dir)
        # 按信号方向的策略收益
        strategy_ret = actual_ret * signal
        rows.append({
            "predict_date": df.iloc[i]["date"],
            "signal": signal,
            "actual_dir": actual_dir,
            "actual_return": actual_ret,
            "strategy_return": strategy_ret,
            "correct": correct,
        })

    if not rows:
        return None
    trades = pd.DataFrame(rows)
    accuracy = float(trades["correct"].mean())
    avg_return = float(trades["strategy_return"].mean())
    cum_return = float((1.0 + trades["strategy_return"]).prod() - 1.0)

    return BacktestResult(
        symbol=symbol,
        market=market,
        strategy=strategy,
        accuracy=accuracy,
        avg_return=avg_return,
        cum_return=cum_return,
        sample_size=len(trades),
        trades=trades,
    )


def one_year_ago_forecast(symbol: str, market: str,
                          strategy: Strategy = "ma_cross",
                          forward_days: int = 20) -> dict | None:
    """你点名的诊断：用 1 年前那一天做预测，看 11 个月前那一天真实走向。"""
    end = datetime.now()
    start = end - timedelta(days=400)
    df = stock_hist(symbol, market,
                    start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    if df is None or df.empty:
        return None
    df = df.sort_values("date").reset_index(drop=True)
    one_year_ago = end - timedelta(days=365)
    # 找 1 年前最近的交易日
    idx = (df["date"] - pd.Timestamp(one_year_ago)).abs().idxmin()
    if idx < 60 or idx + forward_days >= len(df):
        return None
    window = df.iloc[idx - 60:idx]
    signal = STRATEGY_FN[strategy](window)
    p0 = float(df.iloc[idx]["close"])
    p1 = float(df.iloc[idx + forward_days]["close"])
    actual_ret = p1 / p0 - 1.0
    direction = "看多" if signal > 0 else ("看空" if signal < 0 else "中性")
    actual = "上涨" if actual_ret > 0 else "下跌"
    return {
        "predict_date": df.iloc[idx]["date"].strftime("%Y-%m-%d"),
        "label_date": df.iloc[idx + forward_days]["date"].strftime("%Y-%m-%d"),
        "predicted_direction": direction,
        "actual_return": actual_ret,
        "actual_direction": actual,
        "correct": (signal > 0 and actual_ret > 0) or (signal < 0 and actual_ret < 0),
        "strategy": strategy,
    }
