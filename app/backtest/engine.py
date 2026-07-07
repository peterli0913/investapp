"""回测训练框架。

实现你提的训练思路：
    "拿 1 年前的股市信息作为输入，看 11 个月前的真实走势作为标签。"

支持多种策略：
    - mean_reversion  : 近期跌幅大 → 看多反弹
    - momentum        : 近期涨幅大 → 看多延续
    - ma_cross        : 短期均线上穿长期均线 → 看多
    - rsi             : 超卖看多 / 超买看空
    - macd            : MACD 柱方向
    - bollinger       : 布林带上下轨
    - ensemble        : 上面所有信号的加权投票 + ATR 风控 + 新闻情绪
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Literal

import numpy as np
import pandas as pd

from app.backtest.factors import atr_ratio, bollinger, macd, rsi, volume_zscore
from app.services.market_data import stock_hist
from app.utils.logger import get_logger

logger = get_logger("backtest")

Strategy = Literal[
    "mean_reversion", "momentum", "ma_cross",
    "rsi", "macd", "bollinger", "ensemble",
]


# ---------- 经典策略（保留兼容） ----------
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


# ---------- 新策略（基于 factors） ----------
def _signal_rsi(window: pd.DataFrame) -> int:
    sig, _ = rsi(window)
    return sig


def _signal_macd(window: pd.DataFrame) -> int:
    sig, _ = macd(window)
    return sig


def _signal_bollinger(window: pd.DataFrame) -> int:
    sig, _ = bollinger(window)
    return sig


# ---------- Ensemble：加权投票 + ATR 风控 + 新闻情绪 ----------
ENSEMBLE_WEIGHTS = {
    "ma_cross": 1.0,
    "momentum": 0.8,
    "mean_reversion": 0.6,
    "rsi": 1.0,
    "macd": 1.2,
    "bollinger": 0.8,
    "volume": 0.5,
}


def _signal_ensemble(window: pd.DataFrame, *, sentiment: float | None = None) -> int:
    """加权打分。
    - 各因子的 score ∈ [-1, 1] 与权重相乘求和
    - ATR 过高时（>5%）总分权重打 0.6 折，避免高波动期硬上
    - 新闻情绪在 [-0.5, +0.5] 区间内加权
    最终 > 0.4 → +1, < -0.4 → -1, 否则 0。
    """
    if window is None or window.empty or len(window) < 30:
        return 0

    s = window["close"].astype(float)
    # 基线因子（带强度）
    ma_sig = _signal_ma_cross(window)
    ma_score = 0.6 * ma_sig
    mom_sig = _signal_momentum(window)
    mom_score = 0.6 * mom_sig
    mr_sig = _signal_mean_reversion(window)
    mr_score = 0.5 * mr_sig

    rsi_sig, rsi_score = rsi(window)
    macd_sig, macd_score = macd(window)
    boll_sig, boll_score = bollinger(window)
    vol_sig, vol_score = volume_zscore(window)

    parts = {
        "ma_cross": ma_score,
        "momentum": mom_score,
        "mean_reversion": mr_score,
        "rsi": rsi_score,
        "macd": macd_score,
        "bollinger": boll_score,
        "volume": vol_score,
    }
    total = sum(ENSEMBLE_WEIGHTS.get(k, 0.5) * v for k, v in parts.items())
    weight_sum = sum(ENSEMBLE_WEIGHTS.values())
    normalized = total / weight_sum  # ∈ [-1, 1]

    # 新闻情绪
    if sentiment is not None:
        normalized += 0.3 * float(np.clip(sentiment, -1, 1))

    # ATR 风控：高波动 → 信号衰减
    atr = atr_ratio(window)
    if atr > 0.05:
        normalized *= 0.6

    if normalized > 0.25:
        return 1
    if normalized < -0.25:
        return -1
    return 0


STRATEGY_FN: dict[str, Callable[[pd.DataFrame], int]] = {
    "mean_reversion": _signal_mean_reversion,
    "momentum": _signal_momentum,
    "ma_cross": _signal_ma_cross,
    "rsi": _signal_rsi,
    "macd": _signal_macd,
    "bollinger": _signal_bollinger,
    "ensemble": _signal_ensemble,
}


# ---------- 回测结果 ----------
@dataclass
class BacktestResult:
    symbol: str
    market: str
    strategy: str
    accuracy: float                # 方向胜率
    avg_return: float              # 平均收益
    cum_return: float              # 累计收益
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
    strategy: str = "ensemble",
    *,
    lookback_days: int = 60,
    forward_days: int = 20,
    history_years: int = 2,
    step: int = 5,
    sentiment_series: pd.Series | None = None,
) -> BacktestResult | None:
    """对 `symbol/market` 做样本外滚动回测。

    `sentiment_series` 可选，索引为日期、值在 [-1, 1] 的新闻情绪。
    ensemble 策略会读取每个预测日对应的情绪值。
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
    for i in range(lookback_days, len(df) - forward_days, max(1, step)):
        window = df.iloc[i - lookback_days:i]
        if strategy == "ensemble":
            senti = None
            if sentiment_series is not None:
                d = df.iloc[i]["date"]
                try:
                    senti = float(sentiment_series.loc[:d].iloc[-1])
                except Exception:
                    senti = None
            signal = _signal_ensemble(window, sentiment=senti)
        else:
            signal = fn(window)
        if signal == 0:
            continue
        p0 = float(df.iloc[i]["close"])
        p1 = float(df.iloc[i + forward_days]["close"])
        actual_ret = (p1 / p0 - 1.0)
        actual_dir = 1 if actual_ret > 0 else -1
        correct = int(signal == actual_dir)
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
        symbol=symbol, market=market, strategy=strategy,
        accuracy=accuracy, avg_return=avg_return, cum_return=cum_return,
        sample_size=len(trades), trades=trades,
    )


def one_year_ago_forecast(symbol: str, market: str,
                          strategy: str = "ensemble",
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


# ---------- 多策略对比 + 自动选优 ----------
def compare_strategies(
    symbol: str, market: str, *,
    forward_days: int = 20,
    history_years: int = 2,
    strategies: list[str] | None = None,
) -> list[BacktestResult]:
    strategies = strategies or list(STRATEGY_FN.keys())
    out: list[BacktestResult] = []
    for s in strategies:
        r = run_backtest(symbol, market, strategy=s,
                         forward_days=forward_days, history_years=history_years)
        if r is not None:
            out.append(r)
    return out


def best_strategy(results: list[BacktestResult]) -> BacktestResult | None:
    """挑"准确率优先、累计收益次之"的最佳策略。"""
    if not results:
        return None
    return sorted(results, key=lambda r: (r.accuracy, r.cum_return), reverse=True)[0]


def walk_forward_select(
    symbol: str, market: str, *,
    train_years: float = 1.0,
    test_years: float = 1.0,
    forward_days: int = 20,
) -> dict | None:
    """Walk-forward：
        1. 用前 `train_years` 数据评估每个策略（除 ensemble 外）的准确率
        2. 选准确率最高的那个，在后 `test_years` 上跑样本外
        3. 返回训练 / 测试两段的指标，对比是否泛化
    """
    end = datetime.now()
    full_start = end - timedelta(days=int(365 * (train_years + test_years)))
    train_end = end - timedelta(days=int(365 * test_years))

    df = stock_hist(symbol, market,
                    start=full_start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    if df is None or df.empty:
        return None
    df = df.sort_values("date").reset_index(drop=True)

    train_df = df[df["date"] < pd.Timestamp(train_end)]
    test_df = df[df["date"] >= pd.Timestamp(train_end)]
    if len(train_df) < 80 or len(test_df) < forward_days + 30:
        return None

    train_results: dict[str, float] = {}
    for s in ("mean_reversion", "momentum", "ma_cross", "rsi", "macd", "bollinger"):
        fn = STRATEGY_FN[s]
        rows = []
        for i in range(60, len(train_df) - forward_days, 5):
            sig = fn(train_df.iloc[i - 60:i])
            if sig == 0:
                continue
            p0 = float(train_df.iloc[i]["close"])
            p1 = float(train_df.iloc[i + forward_days]["close"])
            rows.append(int(sig == (1 if p1 > p0 else -1)))
        if rows:
            train_results[s] = sum(rows) / len(rows)

    if not train_results:
        return None
    best = max(train_results.items(), key=lambda kv: kv[1])
    best_name = best[0]

    # 在测试集上跑
    test_result = run_backtest(symbol, market, strategy=best_name,
                               forward_days=forward_days, history_years=test_years)

    return {
        "train_scores": train_results,
        "selected": best_name,
        "train_accuracy_of_selected": float(best[1]),
        "test": test_result.to_dict() if test_result else None,
    }
