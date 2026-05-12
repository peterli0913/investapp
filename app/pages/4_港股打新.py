"""模块 4：港股打新。"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("🆕 港股打新 · 这周有啥可以打",
     "把最近能申购的港股新股都列出来，AI 给你算一笔账：这只值不值得打、风险点在哪、怎么操作。")

payload, _ = render_refresh_bar("ipo", "港股打新")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

items = payload.get("items") or []
if not items:
    st.info("当前未抓到港股新股，可稍后再刷新（akshare 接口偶尔不稳定）。")
    st.stop()

for ipo in items:
    name = ipo.get("name") or "新股"
    symbol = ipo.get("symbol", "")
    price = ipo.get("price_range", "-")
    list_date = ipo.get("list_date", "-")
    industry = ipo.get("industry", "-")
    sponsor = ipo.get("sponsor", "-")
    review = ipo.get("review") or {}
    pros = review.get("pros") or []
    cons = review.get("cons") or []
    suggestion = review.get("suggestion", "-")
    rationale = review.get("rationale", "-")

    pros_html = "<br>".join(f"• {p}" for p in pros) or "-"
    cons_html = "<br>".join(f"• {c}" for c in cons) or "-"

    st.markdown(
        f"""
        <div class="card">
            <div class="title">{name} <span style='color:#8B949E;font-size:13px;'>({symbol})</span></div>
            <div class="body">
                <b>所属行业</b>：{industry} &nbsp;|&nbsp;
                <b>招股价</b>：{price} &nbsp;|&nbsp;
                <b>上市日</b>：{list_date} &nbsp;|&nbsp;
                <b>保荐人</b>：{sponsor}<br><br>
                <b>优势</b>：<br>{pros_html}<br><br>
                <b>劣势 / 风险</b>：<br>{cons_html}<br><br>
                <b>建议</b>：<span class="tag">{suggestion}</span><br>
                <span style="color:#8B949E">{rationale}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    news = ipo.get("news") or []
    if news:
        with st.expander(f"查看 {name} 相关新闻（{len(news)}）"):
            for n in news:
                st.markdown(
                    f"- [{n.get('title','')}]({n.get('link','#')})  \n"
                    f"  <span style='color:#8B949E;font-size:12px'>{n.get('source','')} · {n.get('published','')}</span>",
                    unsafe_allow_html=True,
                )
    st.markdown("---")
