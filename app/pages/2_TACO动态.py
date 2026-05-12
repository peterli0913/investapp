"""模块 2：TACO 动态——Trump 新闻 + 股市影响。"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("🇺🇸 TACO 动态",
     "Trump Always Chickens Out · 聚合特朗普相关新闻，并由 AI 给出对美股 / A 股 / 港股的方向性影响。")

payload, _ = render_refresh_bar("taco", "TACO 动态")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

analysis = payload.get("analysis") or "暂无 AI 分析。"
st.markdown(
    f"""
    <div class="card">
        <div class="title">AI 影响分析</div>
        <div class="body" style="white-space: pre-wrap;">{analysis}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("来源新闻")
news = payload.get("news") or []
if not news:
    st.info("暂无新闻。")
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
