"""模块 5：新股推荐。"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("⭐ 新股推荐",
     "综合 A 股 / 港股新股池，结合行业热点筛选推荐标的。")

payload, _ = render_refresh_bar("recommendations", "新股推荐")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

top = payload.get("top") or []
pool = payload.get("pool") or []
hot_news = payload.get("hot_news") or []

st.subheader("🚀 推荐池（AI 建议积极申购）")
if not top:
    st.info("当前推荐池为空。这是常态——AI 只在有把握时给出『积极申购』。可以下方完整池中自选标的。")
else:
    for it in top:
        review = it.get("review") or {}
        pros = "、".join(review.get("pros") or [])
        st.markdown(
            f"""
            <div class="card">
                <div class="title">{it.get('name')} <span class="tag">{it.get('market')}</span></div>
                <div class="body">
                    <b>建议</b>：<span class="tag up">{review.get('suggestion','-')}</span><br>
                    <b>看点</b>：{pros}<br>
                    <span style='color:#8B949E'>{review.get('rationale','')}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.subheader("📋 全部新股池")
for it in pool:
    review = it.get("review") or {}
    with st.expander(f"{it.get('market')} · {it.get('name')} —— {review.get('suggestion','-')}"):
        st.markdown(f"**优势**：{'、'.join(review.get('pros') or []) or '-'}")
        st.markdown(f"**劣势**：{'、'.join(review.get('cons') or []) or '-'}")
        st.markdown(f"**逻辑**：{review.get('rationale','-')}")
        news = it.get("news") or []
        for n in news:
            st.markdown(
                f"- [{n.get('title','')}]({n.get('link','#')})",
                unsafe_allow_html=True,
            )

if hot_news:
    st.subheader("🔥 新股相关热点")
    for n in hot_news:
        st.markdown(
            f"- [{n.get('title','')}]({n.get('link','#')})  \n"
            f"  <span style='color:#8B949E;font-size:12px'>{n.get('source','')} · {n.get('published','')}</span>",
            unsafe_allow_html=True,
        )
