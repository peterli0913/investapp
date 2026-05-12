"""模块 3：热门股票追踪。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui_common import bootstrap_once, hero, pct_html, render_refresh_bar

bootstrap_once()
hero("📊 热门股票追踪",
     "初始关注：胜宏科技 / 极智嘉 / 泡泡马特。可在『设置 / 自选股』中增删。")

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
    df = pd.DataFrame(kline)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="无 K 线数据", showarrow=False)
        return fig
    df["date"] = pd.to_datetime(df["date"])
    fig = go.Figure(data=[go.Candlestick(
        x=df["date"],
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color="#E74C3C",
        decreasing_line_color="#27AE60",
        name="K线",
    )])
    # 均线
    for w, color in ((5, "#E5B864"), (20, "#8B949E")):
        if len(df) >= w:
            ma = df["close"].rolling(w).mean()
            fig.add_trace(go.Scatter(x=df["date"], y=ma, mode="lines",
                                     name=f"MA{w}", line=dict(color=color, width=1.2)))
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#E6EDF3"),
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(gridcolor="#2A2F3A")
    fig.update_yaxes(gridcolor="#2A2F3A")
    return fig


for item in items:
    pct = item.get("recent_pct_20d")
    outlook = item.get("outlook") or {}
    trend = outlook.get("trend", "")
    klass = "up" if trend == "上行" else ("down" if trend == "下行" else "neutral")
    ens = item.get("ensemble_signal", "中性")
    ens_klass = "up" if ens == "看多" else ("down" if ens == "看空" else "neutral")
    senti = item.get("sentiment", 0.0) or 0.0
    senti_klass = "up" if senti > 0.15 else ("down" if senti < -0.15 else "neutral")
    tag_html = (
        f'<span class="tag">{item.get("market","").upper()}</span>'
        f'<span class="tag">近 20 日 {pct_html(pct)}</span>'
        f'<span class="tag {klass}">AI 趋势：{trend}</span>'
        f'<span class="tag {ens_klass}">多因子：{ens}</span>'
        f'<span class="tag {senti_klass}">新闻情绪：{senti:+.2f}</span>'
        f'<span class="tag">均线：{item.get("ma_signal","-")}</span>'
    )
    st.markdown(
        f"""
        <div class="card">
            <div class="title">{item['name']} <span style='color:#8B949E;font-size:13px;'>({item['symbol']})</span></div>
            <div style='margin-bottom:8px'>{tag_html}</div>
            <div class="body"><b>逻辑：</b>{outlook.get('rationale','-')}<br>
                <b>建议：</b>{outlook.get('suggestion','-')}</div>
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
