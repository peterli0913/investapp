"""模块 1：火热板块动态。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.modules.sectors import MARKETS
from app.ui_common import bootstrap_once, hero, pct_html, render_refresh_bar

bootstrap_once()
hero("🔥 板块景气度 · 全球热门赛道动态",
     "覆盖 A 股 / 港股 / 美股 / 日股 / 韩股 五大股市与加密币市场，对 AI 应用、芯片、存储、机器人、大消费、能源 等板块做新闻聚合 + 估值/资金面解读。")

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
        headlines = (payload.get("headlines") or {}).get(market) or []

        if not market_data:
            st.info(f"{market} 暂无数据。")
            continue

        # 顶部：板块涨跌幅柱状图（现在所有市场都能展示）
        chart_title = "📊 今日板块涨跌幅一览" if market != "加密币" else "📊 24 小时涨跌幅一览"
        chart = _pct_bar(market_data)
        if chart:
            st.markdown(f"##### {chart_title}")
            st.plotly_chart(chart, use_container_width=True)

        # 市场要闻：来自常驻 RSS 源
        if headlines:
            with st.expander(f"📰 {market} 市场要闻（{len(headlines)} 条 · 来自财经源 RSS）", expanded=False):
                for n in headlines:
                    title = n.get("title") or "(无标题)"
                    link = n.get("link") or "#"
                    src = n.get("source") or ""
                    pub = n.get("published") or ""
                    st.markdown(
                        f"- [{title}]({link})  \n"
                        f"  <span style='color:#8B949E;font-size:12px'>{src} · {pub}</span>",
                        unsafe_allow_html=True,
                    )
        st.markdown("---")

        # 下面：每个板块/主题的卡片（动态读 payload，不依赖硬编码列表）
        for sector, entry in market_data.items():
            pct = entry.get("pct")
            news = entry.get("news") or []
            summary = entry.get("summary") or "暂无总结。"
            quotes = entry.get("quotes") or []  # 加密币才有

            # 顶部标签：板块涨跌幅 / 加密币也用同样字段
            pct_label = "24 小时涨跌幅" if market == "加密币" else "板块涨跌幅"
            tag = f'<span class="tag">{pct_label}</span>' + pct_html(pct) if pct is not None else ""

            st.markdown(
                f"""
                <div class="card">
                    <div class="title">{sector} &nbsp;&nbsp; {tag}</div>
                    <div class="body" style="line-height:1.8;">{summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 行情明细（加密币 / 美股 ETF / 港股指数 等都会有 quotes）
            if quotes:
                cols = st.columns(min(len(quotes), 4))
                for i, q in enumerate(quotes):
                    ticker = q.get("ticker", "—")
                    price = q.get("price", 0) or 0
                    # 货币符号：加密币 / 美股 用 $；港股 / 日股 / 韩股 不带前缀（指数）
                    prefix = "$" if (market in ("加密币", "美股") and price >= 1) else ""
                    cols[i % len(cols)].metric(
                        ticker,
                        f"{prefix}{price:,.2f}" if price else "—",
                        f"{q.get('pct_24h', 0):+.2f}%",
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
