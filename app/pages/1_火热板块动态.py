"""模块 1：火热板块动态。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.modules.sectors import MARKETS, SECTOR_KEYWORDS
from app.ui_common import bootstrap_once, hero, pct_html, render_refresh_bar

bootstrap_once()
hero("🔥 最近啥板块在火",
     "看看 A股、港股、美股、日股、韩股 五大市场，AI/芯片/存储/机器人/大消费/石油 这些热门板块最近都在干啥。")

payload, _ = render_refresh_bar("sectors", "火热板块动态")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()


def _pct_bar(market_data: dict) -> go.Figure | None:
    """画一个板块涨跌幅横向柱状图（只有 A 股能拿到具体涨跌幅）。"""
    rows = [(s, d.get("pct")) for s, d in market_data.items() if d.get("pct") is not None]
    if not rows:
        return None
    rows.sort(key=lambda x: x[1])
    df = pd.DataFrame(rows, columns=["板块", "涨跌幅"])
    colors = ["#E74C3C" if v > 0 else "#27AE60" for v in df["涨跌幅"]]
    fig = go.Figure(go.Bar(
        x=df["涨跌幅"], y=df["板块"], orientation="h",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in df["涨跌幅"]],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(200, 40 * len(df) + 60),
        margin=dict(l=10, r=40, t=10, b=10),
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#E6EDF3"),
    )
    fig.update_xaxes(gridcolor="#2A2F3A", title="今日涨跌幅 %")
    fig.update_yaxes(gridcolor="#2A2F3A")
    return fig


market_tab = st.tabs(MARKETS)
for tab, market in zip(market_tab, MARKETS):
    with tab:
        market_data = (payload.get("markets") or {}).get(market) or {}
        if not market_data:
            st.info(f"{market} 暂无数据。")
            continue

        # 顶部：板块涨跌幅柱状图（A 股有；其它市场暂时没有就跳过）
        chart = _pct_bar(market_data)
        if chart:
            st.markdown("##### 📊 今日板块涨跌幅一览")
            st.plotly_chart(chart, use_container_width=True)
            st.markdown("---")

        # 下面：每个板块的卡片
        for sector in SECTOR_KEYWORDS.keys():
            entry = market_data.get(sector) or {}
            pct = entry.get("pct")
            news = entry.get("news") or []
            summary = entry.get("summary") or "暂无总结。"
            tag = '<span class="tag">板块涨跌幅</span>' + pct_html(pct) if pct is not None else ""
            with st.container():
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="title">{sector} &nbsp;&nbsp; {tag}</div>
                        <div class="body" style="line-height:1.8;">{summary}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander(f"查看 {sector} 的来源新闻（{len(news)}）"):
                    if not news:
                        st.write("暂无相关新闻。")
                    else:
                        for n in news:
                            title = n.get("title") or "(无标题)"
                            link = n.get("link") or "#"
                            src = n.get("source") or ""
                            pub = n.get("published") or ""
                            st.markdown(
                                f"- [{title}]({link})  \n"
                                f"  <span style='color:#8B949E;font-size:12px'>{src} · {pub}</span>",
                                unsafe_allow_html=True,
                            )
