"""技术因子函数库。

每个函数接收一个含 close / high / low / volume 列的 DataFrame 窗口，
返回 (signal: int, score: float)：
    signal ∈ {-1, 0, 1}：做空 / 中性 / 做多
    score  ∈ [-1, 1]：强度，便于 ensemble 加权投票

所有函数都对数据不足做了兜底，避免抛 NaN。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe(df: pd.DataFrame, min_len: int = 30) -> bool:
    return df is not None and not df.empty and "close" in df.columns and len(df) >= min_len


# ---------- RSI ----------
def rsi(df: pd.DataFrame, period: int = 14) -> tuple[int, float]:
    """RSI < 30 看多反弹；RSI > 70 看空回调。"""
    if not _safe(df, period + 5):
        return 0, 0.0
    delta = df["close"].astype(float).diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    last_gain = float(gain.iloc[-1]) if gain.notna().any() else 0.0
    last_loss = float(loss.iloc[-1]) if loss.notna().any() else 0.0
    if last_gain == 0 and last_loss == 0:
        last = 50.0
    elif last_loss == 0:
        last = 100.0  # 单边上涨极端
    elif last_gain == 0:
        last = 0.0    # 单边下跌极端
    else:
        rs = last_gain / last_loss
        last = 100 - 100 / (1 + rs)
    if last < 30:
        return 1, min(1.0, (30 - last) / 30)
    if last > 70:
        return -1, -min(1.0, (last - 70) / 30)
    return 0, 0.0


# ---------- MACD ----------
def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal_p: int = 9) -> tuple[int, float]:
    """MACD 柱由负转正看多，由正转负看空。同时给出柱子绝对值作为强度。"""
    if not _safe(df, slow + signal_p + 5):
        return 0, 0.0
    c = df["close"].astype(float)
    ema_fast = c.ewm(span=fast, adjust=False).mean()
    ema_slow = c.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig = macd_line.ewm(span=signal_p, adjust=False).mean()
    hist = macd_line - sig
    if len(hist) < 2 or hist.isna().any():
        return 0, 0.0
    last, prev = float(hist.iloc[-1]), float(hist.iloc[-2])
    norm = float(c.iloc[-1]) or 1.0
    strength = float(np.clip(last / (norm * 0.02), -1, 1))  # 用 2% 价格作分母归一化
    if prev <= 0 < last:
        return 1, max(0.3, strength)
    if prev >= 0 > last:
        return -1, min(-0.3, strength)
    if last > 0:
        return 1, max(0.0, strength)
    if last < 0:
        return -1, min(0.0, strength)
    return 0, 0.0


# ---------- 布林带 ----------
def bollinger(df: pd.DataFrame, period: int = 20, std_n: float = 2.0) -> tuple[int, float]:
    """价格触下轨看多反弹，触上轨看空回调。"""
    if not _safe(df, period + 5):
        return 0, 0.0
    c = df["close"].astype(float)
    ma = c.rolling(period).mean()
    sd = c.rolling(period).std()
    upper = ma + std_n * sd
    lower = ma - std_n * sd
    last = float(c.iloc[-1])
    u, l, m = float(upper.iloc[-1]), float(lower.iloc[-1]), float(ma.iloc[-1])
    width = max(u - l, 1e-9)
    pos = (last - m) / (width / 2)  # -1: 下轨；+1: 上轨
    if last <= l:
        return 1, min(1.0, abs(pos))
    if last >= u:
        return -1, -min(1.0, abs(pos))
    return 0, float(np.clip(-pos * 0.3, -0.3, 0.3))


# ---------- ATR 风控（不直接给方向，给"是否高波动"打分） ----------
def atr_ratio(df: pd.DataFrame, period: int = 14) -> float:
    """返回 ATR / close 比例。高波动时 ensemble 应该减仓位。"""
    if not _safe(df, period + 5) or "high" not in df.columns or "low" not in df.columns:
        return 0.0
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    prev_close = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    atr_v = tr.rolling(period).mean()
    if atr_v.isna().all():
        return 0.0
    return float(atr_v.iloc[-1] / max(float(c.iloc[-1]), 1e-9))


# ---------- 量能异动 ----------
def volume_zscore(df: pd.DataFrame, period: int = 20) -> tuple[int, float]:
    """近期成交量相对 20 日均量异常放大 + 当日红盘 → 看多；反之 → 看空。"""
    if not _safe(df, period + 5) or "volume" not in df.columns:
        return 0, 0.0
    v = df["volume"].astype(float)
    mu = v.rolling(period).mean()
    sd = v.rolling(period).std().replace(0, np.nan)
    z = (v - mu) / sd
    last_z = float(z.iloc[-1]) if z.notna().any() else 0.0
    if abs(last_z) < 1.5:
        return 0, 0.0
    c = df["close"].astype(float)
    rising = c.iloc[-1] > c.iloc[-2] if len(c) >= 2 else True
    direction = 1 if rising else -1
    return direction, float(np.clip(direction * abs(last_z) / 3, -1, 1))


# ---------- 综合打包 ----------
def all_signals(df: pd.DataFrame) -> dict[str, tuple[int, float]]:
    return {
        "rsi": rsi(df),
        "macd": macd(df),
        "bollinger": bollinger(df),
        "volume": volume_zscore(df),
    }
