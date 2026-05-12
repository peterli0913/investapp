"""模块 2：国际动态 · 大白话讲最近全球发生了啥。

收集特朗普、美联储、地缘冲突、央行决议、大宗商品、AI 监管等大事件，
AI 给出对股市/加密币的影响。
"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("🌍 国际动态 · 大白话讲最近全球发生了啥",
     "特朗普 / 美联储 / 中美关系 / 地缘冲突 / 央行决议 / 油价金价 / AI 监管。AI 帮你把这些事整理成时间轴，再告诉你对股市意味着啥。")

payload, _ = render_refresh_bar("taco", "国际动态")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

# 1. 整体看法
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
events = payload.get("events") or []
news_count = payload.get("news_count", len(payload.get("news") or []))

# 类型徽章颜色映射
CAT_COLORS = {
    "政治": "#E5B864",
    "经济": "#3F88C5",
    "地缘": "#E74C3C",
    "科技": "#9B59B6",
    "能源": "#F39C12",
    "监管": "#16A085",
    "央行": "#5DADE2",
    "其它": "#8B949E",
}
CAT_EMOJI = {
    "政治": "🏛️",
    "经济": "💰",
    "地缘": "🌐",
    "科技": "💻",
    "能源": "⛽",
    "监管": "⚖️",
    "央行": "🏦",
    "其它": "📰",
}


st.subheader(f"🕐 最近发生了哪些大事（共 {len(events)} 件，来自 {news_count} 条新闻）")

if not events:
    st.error(
        "没抓到任何事件 ❌\n\n"
        "可能原因：(1) AI 调用失败或超时；(2) Google News RSS 临时不可达；(3) 没配 LLM Key。"
        "建议先到『设置 / 自选股』点 🔌 测试 LLM 连接，再回来点立即刷新。"
    )
else:
    # 按类型筛选
    all_cats = sorted({ev.get("category", "其它") for ev in events})
    sel_cats = st.multiselect(
        "按类型筛选（默认全部）",
        options=all_cats,
        default=all_cats,
    )

    for ev in events:
        cat = ev.get("category") or "其它"
        if cat not in sel_cats:
            continue
        date = ev.get("date") or "—"
        title = ev.get("title") or "未知事件"
        plain = ev.get("plain") or ""
        impact = ev.get("impact") or ""
        links = ev.get("links") or []
        color = CAT_COLORS.get(cat, "#8B949E")
        emoji = CAT_EMOJI.get(cat, "📰")

        st.markdown(
            f"""
            <div class="card" style="border-left: 4px solid {color};">
                <div class="meta">
                    📅 {date} &nbsp;·&nbsp;
                    <span style="background-color: {color}22; color: {color}; padding: 2px 8px; border-radius: 4px; font-weight: 600;">
                        {emoji} {cat}
                    </span>
                </div>
                <div class="title">{title}</div>
                <div class="body" style="line-height:1.8;">
                    <b>📝 这事是怎么回事</b><br>{plain}
                    <br><br>
                    <b>📊 对市场意味着</b><br>{impact}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if links:
            with st.expander(f"看这条事件的相关新闻（{len(links)}）"):
                for ln in links:
                    st.markdown(f"- [{ln.get('title','')}]({ln.get('url','#')})")

# 3. 全部来源新闻（备查）
st.markdown("---")
with st.expander(f"📰 全部抓到的新闻（{news_count} 条）"):
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
