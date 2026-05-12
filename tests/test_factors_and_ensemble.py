"""factors + ensemble + sentiment 的纯逻辑单元测试。

不依赖真实行情数据源（akshare/yfinance/RSS 可能在 CI 中没网络），
全部用 numpy / pandas 合成 K 线。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backtest.engine import (  # noqa: E402
    STRATEGY_FN, _signal_ensemble, run_backtest,
)
from app.backtest.factors import (  # noqa: E402
    atr_ratio, bollinger, macd, rsi, volume_zscore,
)
from app.services.sentiment import (  # noqa: E402
    headlines_sentiment, keyword_score,
)


def _make_df(prices, vol=None):
    n = len(prices)
    s = pd.Series(prices, dtype=float)
    high = s * 1.01
    low = s * 0.99
    if vol is None:
        vol = np.full(n, 1e6)
    return pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n, freq="B"),
        "open": s, "close": s, "high": high, "low": low, "volume": vol,
    })


def test_rsi_extremes():
    # 单调上涨 → RSI 应 > 70（超买，看空）
    up = _make_df(np.linspace(100, 200, 60))
    sig, _ = rsi(up)
    assert sig == -1, "持续上涨 RSI 应该看空"

    # 单调下跌 → RSI 应 < 30（超卖，看多）
    down = _make_df(np.linspace(200, 100, 60))
    sig, _ = rsi(down)
    assert sig == 1, "持续下跌 RSI 应该看多"


def test_bollinger_band_touch():
    # 平稳后突然冲高 → 触上轨
    base = np.full(50, 100.0)
    spike = np.array([130, 135, 140])
    df = _make_df(np.concatenate([base, spike]))
    sig, _ = bollinger(df)
    assert sig == -1, "价格冲到布林上轨应看空"


def test_macd_runs():
    # 仅验证不报错并返回合法 signal
    np.random.seed(1)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    sig, score = macd(_make_df(prices))
    assert sig in (-1, 0, 1)
    assert -1 <= score <= 1


def test_volume_zscore_burst():
    # 大部分时间正常，最后一根放量上涨 → 看多
    base_v = np.full(40, 1e6)
    burst_v = np.array([5e6])
    vol = np.concatenate([base_v, burst_v])
    prices = np.concatenate([np.full(40, 100.0), np.array([102.0])])
    df = _make_df(prices, vol=vol)
    sig, _ = volume_zscore(df)
    assert sig == 1, "放量上涨应该看多"


def test_atr_ratio_bounds():
    df = _make_df(np.linspace(100, 110, 60))
    r = atr_ratio(df)
    assert 0.0 <= r < 0.5, "ATR/price 应该是个小的正数"


def test_ensemble_uptrend():
    # 缓慢稳定上涨：ensemble 至少不该看空
    prices = np.linspace(100, 130, 80)
    df = _make_df(prices)
    s = _signal_ensemble(df, sentiment=0.4)
    assert s >= 0, "稳定上涨 + 正情绪不应给出看空信号"


def test_ensemble_downtrend():
    # 稳定下跌
    prices = np.linspace(130, 100, 80)
    df = _make_df(prices)
    s = _signal_ensemble(df, sentiment=-0.4)
    assert s <= 0, "稳定下跌 + 负情绪不应给出看多信号"


def test_all_strategies_safe_on_short_data():
    # 窗口太短，所有策略都应该返回 0（不报错）
    df = _make_df(np.linspace(100, 105, 10))
    for name, fn in STRATEGY_FN.items():
        v = fn(df)
        assert v in (-1, 0, 1), f"{name} 返回非法值 {v}"


def test_sentiment_keyword():
    assert keyword_score("公司发布利好公告，业绩超预期，股价大涨") > 0.3
    assert keyword_score("公司被立案调查，业绩亏损，股价暴跌") < -0.3
    assert keyword_score("公司发布定期报告。") == 0.0


def test_sentiment_aggregate():
    titles = [
        "公司利好不断，订单超预期",
        "重磅签约新客户",
        "无关公告",
    ]
    s = headlines_sentiment(titles)
    assert s > 0


def test_backtest_smoke_synthetic(monkeypatch):
    """绕过真实数据源，用 patched stock_hist 跑完整回测流程。"""
    np.random.seed(42)
    n = 600
    # 用更明显的趋势 + 高波动，确保所有策略都能触发信号
    drift = np.linspace(0, 1.5, n)
    noise = np.cumsum(np.random.randn(n) * 0.8)
    prices = 100 + drift * 100 + noise
    df = _make_df(prices, vol=np.random.uniform(0.8e6, 1.2e6, n))

    import app.backtest.engine as eng
    monkeypatch.setattr(eng, "stock_hist", lambda *a, **kw: df)

    # ma_cross 在非平稳序列上几乎总是非零信号
    r = run_backtest("FAKE", "a", strategy="ma_cross",
                     forward_days=20, history_years=2, step=5)
    assert r is not None
    assert r.sample_size > 0
    assert 0.0 <= r.accuracy <= 1.0

    # ensemble 也应能跑通（不强制要求一定有样本，但不能抛异常）
    r2 = run_backtest("FAKE", "a", strategy="ensemble",
                     forward_days=20, history_years=2, step=5)
    if r2 is not None:
        assert 0.0 <= r2.accuracy <= 1.0


if __name__ == "__main__":
    # 允许 `python tests/test_factors_and_ensemble.py` 直接运行
    import inspect
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            if "monkeypatch" in inspect.signature(fn).parameters:
                continue  # 跳过 pytest fixture
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as e:
                print(f"  FAIL {name}: {e}")
                raise
    print("ALL OK")
