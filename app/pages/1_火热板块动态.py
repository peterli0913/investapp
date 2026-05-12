"""模块 1：火热板块动态。"""
from __future__ import annotations

import streamlit as st

from app.modules.sectors import MARKETS, SECTOR_KEYWORDS
from app.ui_common import bootstrap_once, hero, pct_html, render_refresh_bar

bootstrap_once()
hero("🔥 火热板块动态",
     "覆盖 港股 / 美股 / A 股，对 AI 应用、芯片、存储、机器人、大消费、石油 等板块进行新闻聚合与 AI 解读。")

payload, _ = render_refresh_bar("sectors", "火热板块动态")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

market_tab = st.tabs(MARKETS)
for tab, market in zip(market_tab, MARKETS):
    with tab:
        market_data = (payload.get("markets") or {}).get(market) or {}
        if not market_data:
            st.info(f"{market} 暂无数据。")
            continue
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
                        <div class="body">{summary}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander(f"查看 {sector} 来源新闻（{len(news)}）"):
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
