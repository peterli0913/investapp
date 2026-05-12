"""模块 6：回测训练。

实现你描述的训练 / 验证流程：
    用 1 年前的股市信息作为输入，看 11 个月前的真实走势作为标签。
另外也提供完整 2 年滚动回测，便于挑选最适合每只标的的策略。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.backtest.engine import STRATEGY_FN, one_year_ago_forecast, run_backtest
from app.storage.db import get_watchlist
from app.ui_common import bootstrap_once, hero, inject_theme

bootstrap_once()
inject_theme()
hero("🧪 回测训练 · 策略验证",
     "用前两年的公开行情滚动回测，并用『1 年前预测 → 11 个月前真实走势』做样本外验证。")

wl = get_watchlist()
if not wl:
    st.warning("自选股为空，请到『设置 / 自选股』先添加。")
    st.stop()

col1, col2, col3 = st.columns([3, 3, 3])
with col1:
    pick = st.selectbox(
        "选择股票",
        wl,
        format_func=lambda w: f"{w['name']} ({w['symbol']}) · {w['market'].upper()}",
    )
with col2:
    strategy = st.selectbox("策略", list(STRATEGY_FN.keys()), index=2)
with col3:
    forward_days = st.slider("预测窗口（交易日）", 5, 60, 20, 5)

run_btn = st.button("运行回测", type="primary")

if run_btn:
    with st.spinner("拉取历史行情并回测中…"):
        result = run_backtest(
            pick["symbol"], pick["market"],
            strategy=strategy, forward_days=forward_days,
        )
        forecast = one_year_ago_forecast(
            pick["symbol"], pick["market"],
            strategy=strategy, forward_days=forward_days,
        )

    if not result:
        st.error("行情数据不足，无法回测。")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("方向胜率", f"{result.accuracy*100:.1f}%")
        c2.metric("平均收益", f"{result.avg_return*100:.2f}%")
        c3.metric("累计收益", f"{result.cum_return*100:.2f}%")
        c4.metric("样本数", str(result.sample_size))

        st.subheader("逐笔预测明细（最近 30 笔）")
        df = result.trades.tail(30).copy()
        df["actual_return"] = (df["actual_return"] * 100).round(2)
        df["strategy_return"] = (df["strategy_return"] * 100).round(2)
        df["correct"] = df["correct"].map({1: "✅", 0: "❌"})
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("策略收益曲线")
        eq = (1 + result.trades["strategy_return"]).cumprod()
        eq.index = result.trades["predict_date"]
        st.line_chart(eq, height=260)

    st.markdown("---")
    st.subheader("『1 年前预测 → 11 个月前真实走势』诊断")
    if not forecast:
        st.info("可能因数据点不足无法生成此诊断。可尝试更换股票或缩短预测窗口。")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("预测日期", forecast["predict_date"])
        c2.metric("标签日期", forecast["label_date"])
        c3.metric("结论", "✅ 命中" if forecast["correct"] else "❌ 未命中")
        st.write(
            f"- 策略预测方向：**{forecast['predicted_direction']}**\n"
            f"- 真实方向：**{forecast['actual_direction']}**（{forecast['actual_return']*100:.2f}%）\n"
            f"- 使用策略：`{forecast['strategy']}`"
        )

st.markdown("---")
st.markdown(
    """
    ### 关于策略
    - **mean_reversion** 均值回归：近 20 日大跌看多反弹，反之看空。
    - **momentum** 动量：近 20 日上涨延续看多。
    - **ma_cross** 均线交叉：MA5 上穿 MA20 看多，下穿看空，多数情况下作为基准较稳。

    后续可以接入 LLM 在 backtest 框架里做 **行情+新闻** 的联合预测，
    并把每次预测结果存进 `module_history`，长期统计每个策略对每只股的胜率，
    自动选择"最适合该标的"的策略组合。
    """
)
