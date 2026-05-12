"""模块 3：热门股票追踪。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.ui_common import bootstrap_once, hero, pct_html, render_refresh_bar

bootstrap_once()
hero("📊 我的关注股 · 每日动态 + 操作建议",
     "默认盯着这三只：胜宏科技 / 极智嘉 / 泡泡玛特。想换其它的去『设置 / 自选股』加。")

payload, _ = render_refresh_bar("tracked", "热门股票追踪")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

items = payload.get("items") or []
if not items:
    st.info("自选股为空，请到『设置』页面添加。")
    st.stop()


def _kline_chart(kline: list[dict]) -> go.Figure:
    """K 线 + 均线 + 成交量子图。"""
    if not kline:
        fig = go.Figure()
        fig.add_annotation(text="无 K 线数据", showarrow=False)
        return fig
    df = pd.DataFrame(kline)
    df["date"] = pd.to_datetime(df["date"])

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.72, 0.28], vertical_spacing=0.02,
        subplot_titles=("", ""),
    )
    # K 线
    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color="#E74C3C",
        decreasing_line_color="#27AE60",
        name="K线",
        showlegend=False,
    ), row=1, col=1)
    # 均线
    for w, color in ((5, "#E5B864"), (20, "#8B949E"), (60, "#3F88C5")):
        if len(df) >= w:
            ma = df["close"].rolling(w).mean()
            fig.add_trace(go.Scatter(
                x=df["date"], y=ma, mode="lines",
                name=f"MA{w}", line=dict(color=color, width=1.2),
            ), row=1, col=1)
    # 成交量（红涨绿跌）
    vol_colors = ["#E74C3C" if c >= o else "#27AE60"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["volume"],
        marker_color=vol_colors,
        name="成交量",
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#E6EDF3"),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(gridcolor="#2A2F3A")
    fig.update_yaxes(gridcolor="#2A2F3A")
    return fig


def _market_currency(market: str) -> str:
    m = (market or "").lower()
    return {"a": "¥", "hk": "HK$", "us": "US$"}.get(m, "")


for item in items:
    pct = item.get("recent_pct_20d")
    outlook = item.get("outlook") or {}
    trend = outlook.get("trend", "")
    klass = "up" if trend == "上行" else ("down" if trend == "下行" else "neutral")
    ens = item.get("ensemble_signal", "中性")
    ens_klass = "up" if ens == "看多" else ("down" if ens == "看空" else "neutral")
    senti = item.get("sentiment", 0.0) or 0.0
    senti_klass = "up" if senti > 0.15 else ("down" if senti < -0.15 else "neutral")
    metrics = item.get("metrics") or {}
    currency = _market_currency(item.get("market", ""))

    # 顶部：股票名 + 标签
    tag_html = (
        f'<span class="tag">{item.get("market","").upper()}</span>'
        f'<span class="tag">近 20 日 {pct_html(pct)}</span>'
        f'<span class="tag {klass}">AI 趋势：{trend}</span>'
        f'<span class="tag {ens_klass}">多因子：{ens}</span>'
        f'<span class="tag {senti_klass}">新闻情绪：{senti:+.2f}</span>'
    )
    st.markdown(
        f"""
        <div class="card">
            <div class="title">{item['name']} <span style='color:#8B949E;font-size:13px;'>({item['symbol']})</span></div>
            <div style='margin-bottom:8px'>{tag_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 今日股价 / 涨跌 / 成交量 4 个 metric
    if metrics:
        last_close = metrics.get("last_close")
        today_pct = metrics.get("today_pct")
        m_cols = st.columns(4)
        m_cols[0].metric(
            "最新价",
            f"{currency}{last_close:.2f}" if last_close else "—",
            f"{today_pct:+.2f}%" if today_pct is not None else None,
        )
        m_cols[1].metric(
            f"日内高 / 低 ({metrics.get('last_date','-')})",
            f"{metrics.get('last_high', 0):.2f} / {metrics.get('last_low', 0):.2f}" if last_close else "—",
        )
        m_cols[2].metric("当日成交量", metrics.get("volume_str", "—"))
        m_cols[3].metric("当日成交额", metrics.get("amount_str", "—"))

    # AI 建议
    st.markdown(
        f"""
        <div class="card">
            <div class="body" style="line-height:1.8;">
                <b>💡 我的看法</b>：{outlook.get('rationale','-')}<br>
                <b>🎯 怎么操作</b>：{outlook.get('suggestion','-')}<br>
                <span style='color:#8B949E;font-size:12px;'>均线信号：{item.get('ma_signal','-')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.plotly_chart(_kline_chart(item.get("kline") or []), use_container_width=True)
    with st.expander(f"查看 {item['name']} 来源新闻（{len(item.get('news') or [])}）"):
        for n in item.get("news") or []:
            title = n.get("title") or ""
            link = n.get("link") or "#"
            src = n.get("source") or ""
            pub = n.get("published") or ""
            st.markdown(
                f"- [{title}]({link})  \n"
                f"  <span style='color:#8B949E;font-size:12px'>{src} · {pub}</span>",
                unsafe_allow_html=True,
            )
    st.markdown("---")
