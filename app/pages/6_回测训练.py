"""模块 6：回测训练。

实现你描述的训练 / 验证流程：
    用 1 年前的股市信息作为输入，看 11 个月前的真实走势作为标签。
另外提供：
    - 7 种策略横向对比（含 ensemble 加权投票）
    - Walk-forward：训练集选最优策略，测试集验证泛化
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.backtest.engine import (
    STRATEGY_FN, best_strategy, compare_strategies,
    one_year_ago_forecast, run_backtest, walk_forward_select,
)
from app.storage.db import get_watchlist
from app.ui_common import bootstrap_once, hero, inject_theme

bootstrap_once()
inject_theme()
hero("🧪 看看 AI 的判断准不准",
     "用过去两年的真实行情来模拟：如果当时按这套策略买卖，胜率有多高、能赚多少。重点是『1 年前预测 → 11 个月前的真实涨跌』。")

wl = get_watchlist()
if not wl:
    st.warning("自选股为空，请到『设置 / 自选股』先添加。")
    st.stop()

col1, col2, col3 = st.columns([3, 3, 2])
with col1:
    pick = st.selectbox(
        "选择股票",
        wl,
        format_func=lambda w: f"{w['name']} ({w['symbol']}) · {w['market'].upper()}",
    )
with col2:
    mode = st.selectbox("模式", ["策略横向对比 (推荐)", "单策略详细回测", "Walk-Forward 训练+测试"])
with col3:
    forward_days = st.slider("预测窗口（交易日）", 5, 60, 20, 5)

run_btn = st.button("运行回测", type="primary")
st.markdown("---")


def _render_metric_row(r):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("方向胜率", f"{r.accuracy*100:.1f}%")
    c2.metric("平均收益", f"{r.avg_return*100:.2f}%")
    c3.metric("累计收益", f"{r.cum_return*100:.2f}%")
    c4.metric("样本数", str(r.sample_size))


if run_btn:
    if mode.startswith("策略横向对比"):
        with st.spinner("跨 7 个策略回测中（拉取 2 年历史 + 滚动评估）…"):
            results = compare_strategies(pick["symbol"], pick["market"],
                                         forward_days=forward_days)
        if not results:
            st.error("行情数据不足，无法回测。")
        else:
            df = pd.DataFrame([r.to_dict() for r in results])
            df["accuracy"] = (df["accuracy"] * 100).round(2)
            df["avg_return"] = (df["avg_return"] * 100).round(2)
            df["cum_return"] = (df["cum_return"] * 100).round(2)
            df = df.rename(columns={
                "strategy": "策略", "accuracy": "胜率%",
                "avg_return": "平均收益%", "cum_return": "累计收益%",
                "sample_size": "样本数",
            })
            df = df.drop(columns=["symbol", "market"])
            df = df.sort_values("胜率%", ascending=False)
            st.subheader("各策略对比")
            st.dataframe(df, use_container_width=True, hide_index=True)

            best = best_strategy(results)
            if best:
                st.success(f"🏆 最佳策略：**{best.strategy}**（胜率 {best.accuracy*100:.1f}%，累计 {best.cum_return*100:.2f}%）")
                st.subheader(f"{best.strategy} 收益曲线")
                eq = (1 + best.trades["strategy_return"]).cumprod()
                eq.index = best.trades["predict_date"]
                st.line_chart(eq, height=260)

    elif mode.startswith("单策略"):
        strategy = st.selectbox("策略", list(STRATEGY_FN.keys()),
                                index=list(STRATEGY_FN.keys()).index("ensemble"),
                                key="single_strat")
        with st.spinner("回测中…"):
            r = run_backtest(pick["symbol"], pick["market"],
                             strategy=strategy, forward_days=forward_days)
        if not r:
            st.error("行情数据不足。")
        else:
            _render_metric_row(r)
            st.subheader("逐笔预测明细（最近 30 笔）")
            tail = r.trades.tail(30).copy()
            tail["actual_return"] = (tail["actual_return"] * 100).round(2)
            tail["strategy_return"] = (tail["strategy_return"] * 100).round(2)
            tail["correct"] = tail["correct"].map({1: "✅", 0: "❌"})
            st.dataframe(tail, use_container_width=True, hide_index=True)
            st.subheader("策略收益曲线")
            eq = (1 + r.trades["strategy_return"]).cumprod()
            eq.index = r.trades["predict_date"]
            st.line_chart(eq, height=260)

    else:  # Walk-Forward
        with st.spinner("Walk-Forward：用前 1 年训练 + 后 1 年测试…"):
            result = walk_forward_select(
                pick["symbol"], pick["market"], forward_days=forward_days,
                train_years=1.0, test_years=1.0,
            )
        if not result:
            st.error("数据不足以拆分训练/测试集。")
        else:
            st.subheader("训练集各策略胜率")
            tr = pd.DataFrame(
                [{"策略": k, "训练胜率%": round(v*100, 2)} for k, v in result["train_scores"].items()]
            ).sort_values("训练胜率%", ascending=False)
            st.dataframe(tr, use_container_width=True, hide_index=True)
            st.success(f"🎯 训练集选出最佳策略：**{result['selected']}**（{result['train_accuracy_of_selected']*100:.1f}%）")

            t = result["test"]
            if t:
                st.subheader("测试集（样本外）表现")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("胜率", f"{t['accuracy']*100:.1f}%")
                c2.metric("平均收益", f"{t['avg_return']*100:.2f}%")
                c3.metric("累计收益", f"{t['cum_return']*100:.2f}%")
                c4.metric("样本数", str(t["sample_size"]))
                gap = result['train_accuracy_of_selected'] - t['accuracy']
                if gap > 0.1:
                    st.warning(f"⚠️ 训练-测试 胜率差 {gap*100:.1f}%，存在过拟合迹象。")
                else:
                    st.info(f"训练-测试 胜率差 {gap*100:+.1f}%，泛化良好。")

    # 始终额外跑一次"1 年前 → 11 个月前"诊断（用 ensemble）
    st.markdown("---")
    st.subheader("『1 年前预测 → 11 个月前真实』诊断（ensemble）")
    forecast = one_year_ago_forecast(pick["symbol"], pick["market"],
                                     strategy="ensemble", forward_days=forward_days)
    if not forecast:
        st.info("数据点不足，无法生成此诊断。")
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
    ### 策略说明
    | 策略 | 思路 |
    |---|---|
    | **ensemble** | 多因子加权投票 + ATR 风控 + 新闻情绪。一般最稳。 |
    | mean_reversion | 近期大跌看反弹 |
    | momentum | 近期上涨延续 |
    | ma_cross | MA5 / MA20 交叉 |
    | rsi | 14 日 RSI 超买超卖 |
    | macd | MACD 柱方向转换 |
    | bollinger | 布林带上下轨触及 |

    ### 选择建议
    1. **先看『策略横向对比』** → 看哪个策略最适合这只股
    2. **再看 Walk-Forward** → 确认这个最佳策略不是过拟合到训练集
    3. **最后用『1 年前→11 个月前』** 做一次独立校验
    """
)
