"""模块 4：港股打新。"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("🆕 港股打新 · 招股日历与申购建议",
     "聚合港股新股招股日历，结合估值对标、基石质量、行业景气度、市场情绪等维度给出研报式打新建议。")

payload, _ = render_refresh_bar("ipo", "港股打新")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

items = payload.get("items") or []
data_source = payload.get("data_source", "unknown")
total = payload.get("total", len(items))

# 数据源标识 + 总数
src_label = {
    "akshare": "🟢 akshare（东方财富 / 新浪）",
    "google_news+llm": "🟡 Google News + AI 提取（兜底）",
    "none": "🔴 无数据源可用",
    "unknown": "—",
}.get(data_source, data_source)
st.caption(f"数据来源：{src_label} · 抓取 {total} 条新股")

if not items:
    st.info(
        "本次未抓到港股新股。原因可能是：\n\n"
        "1. akshare 接口短暂不可用（东方财富 / 新浪都返回空）\n"
        "2. Google News 没有近期的『港股 招股』相关报道（淡季）\n"
        "3. LLM 未配置 Key，无法从新闻中提取结构化数据\n\n"
        "建议稍后再刷新；或到『设置』测试 LLM 连接。"
    )
    st.stop()

for ipo in items:
    name = ipo.get("name") or ipo.get("股票简称") or "新股"
    symbol = ipo.get("symbol", "") or ipo.get("代码", "")
    price = ipo.get("price_range", "-") or ipo.get("招股价", "-")
    list_date = ipo.get("list_date", "-") or ipo.get("上市日期", "-")
    industry = ipo.get("industry", "-") or ipo.get("行业", "-")
    sponsor = ipo.get("sponsor", "-") or ipo.get("保荐人", "-")
    highlight = ipo.get("highlight", "")
    src_tag = ipo.get("_source", "")
    review = ipo.get("review") or {}
    pros = review.get("pros") or []
    cons = review.get("cons") or []
    suggestion = review.get("suggestion", "-")
    rationale = review.get("rationale", "-")

    pros_html = "<br>".join(f"• {p}" for p in pros) or "-"
    cons_html = "<br>".join(f"• {c}" for c in cons) or "-"

    src_html = f'<span class="tag">{src_tag}</span>' if src_tag else ''
    highlight_html = (f'<b>🔍 核心看点</b><br>{highlight}<br><br>' if highlight else '')
    st.markdown(
        f"""
        <div class="card">
            <div class="title">{name} <span style='color:#8B949E;font-size:13px;'>({symbol})</span> {src_html}</div>
            <div class="body" style="line-height:1.85;">
                <b>所属行业</b>：{industry} &nbsp;|&nbsp;
                <b>招股价</b>：{price} &nbsp;|&nbsp;
                <b>上市日</b>：{list_date} &nbsp;|&nbsp;
                <b>保荐人</b>：{sponsor}<br><br>
                {highlight_html}
                <b>👍 看点</b><br>{pros_html}<br><br>
                <b>⚠️ 风险点</b><br>{cons_html}<br><br>
                <b>📋 申购建议</b>：<span class="tag">{suggestion}</span><br>
                <span style="color:#8B949E;font-size:13px;line-height:1.8;">{rationale}</span>
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
