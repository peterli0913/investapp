"""模块 2：TACO 动态——Trump 新闻 + 大白话事件解读 + 股市影响。"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("🇺🇸 特朗普动态 · 大白话讲他在折腾啥",
     "TACO = Trump Always Chickens Out。我们把他最近的新闻整理成事件时间轴，并告诉你这事对股市意味着啥。")

payload, _ = render_refresh_bar("taco", "TACO 动态")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

# 1. 整体影响分析（大白话总结）
analysis = payload.get("analysis") or "暂无 AI 分析。"
st.markdown(
    f"""
    <div class="card">
        <div class="title">📌 这两天的总体看法</div>
        <div class="body" style="white-space: pre-wrap; line-height:1.8;">{analysis}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 2. 事件时间轴
st.subheader("🕐 最近发生了哪些事")
events = payload.get("events") or []

if not events:
    st.info("AI 还没给出结构化事件清单。可能是没配 LLM Key，或这次抓的新闻太少。")
else:
    for ev in events:
        date = ev.get("date") or "—"
        title = ev.get("title") or "未知事件"
        plain = ev.get("plain") or ""
        impact = ev.get("impact") or ""
        links = ev.get("links") or []

        st.markdown(
            f"""
            <div class="card">
                <div class="meta">📅 {date}</div>
                <div class="title">{title}</div>
                <div class="body" style="line-height:1.8;">
                    <b>📝 这事是怎么回事</b><br>{plain}
                    <br><br>
                    <b>📊 对股市意味着</b><br>{impact}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if links:
            with st.expander(f"查看这条事件的相关新闻（{len(links)} 条）"):
                for ln in links:
                    st.markdown(f"- [{ln.get('title','')}]({ln.get('url','#')})")

# 3. 全部来源新闻（备查）
st.markdown("---")
with st.expander(f"📰 全部抓到的特朗普相关新闻（{len(payload.get('news') or [])} 条）"):
    for n in payload.get("news") or []:
        title = n.get("title") or "(无标题)"
        link = n.get("link") or "#"
        src = n.get("source") or ""
        pub = n.get("published") or ""
        st.markdown(
            f"- [{title}]({link})  \n"
            f"  <span style='color:#8B949E;font-size:12px'>{src} · {pub}</span>",
            unsafe_allow_html=True,
        )
