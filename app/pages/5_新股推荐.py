"""模块 5：新股推荐。

明确分港股 / A 股 两块，港股突出（散户主要打新场景）。
"""
from __future__ import annotations

import streamlit as st

from app.ui_common import bootstrap_once, hero, render_refresh_bar

bootstrap_once()
hero("⭐ 新股推荐 · 港股优先",
     "把最近能买的港股、A 股新股全抓回来，让 AI 给你过一遍：哪些值得申购、哪些观望、哪些直接放过。")

payload, _ = render_refresh_bar("recommendations", "新股推荐")
st.markdown("---")

if not payload:
    st.warning("还没有数据。点击右上角的『立即刷新』按钮开始第一次抓取。")
    st.stop()

top = payload.get("top") or []
pool = payload.get("pool") or []
hot_news = payload.get("hot_news") or []

# 按市场分组
hk_pool = [p for p in pool if "港" in (p.get("market") or "")]
a_pool = [p for p in pool if "A" in (p.get("market") or "") or "a" in (p.get("market") or "").lower()]
other_pool = [p for p in pool if p not in hk_pool and p not in a_pool]

hk_top = [p for p in top if "港" in (p.get("market") or "")]
a_top = [p for p in top if "A" in (p.get("market") or "") or "a" in (p.get("market") or "").lower()]


def _render_card(it: dict, suggestion_klass: str = "up"):
    review = it.get("review") or {}
    pros = "、".join(review.get("pros") or []) or "—"
    cons = "、".join(review.get("cons") or []) or "—"
    st.markdown(
        f"""
        <div class="card">
            <div class="title">{it.get('name')} <span class="tag">{it.get('market')}</span></div>
            <div class="body" style="line-height:1.8;">
                <b>建议</b>：<span class="tag {suggestion_klass}">{review.get('suggestion','-')}</span><br>
                <b>👍 看点</b>：{pros}<br>
                <b>⚠️ 风险</b>：{cons}<br>
                <span style='color:#8B949E'>{review.get('rationale','')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    news = it.get("news") or []
    if news:
        with st.expander(f"看 {it.get('name')} 的相关新闻（{len(news)}）"):
            for n in news:
                st.markdown(
                    f"- [{n.get('title','')}]({n.get('link','#')})",
                    unsafe_allow_html=True,
                )


# ============= 港股部分（优先） =============
st.subheader("🇭🇰 港股新股")

st.markdown("**🚀 港股 · AI 建议积极申购**")
if not hk_top:
    st.info("当前港股推荐池里 AI 没标『积极申购』。要么是新股不够吸引力，要么是 AI 在观望——这是常态。下面是完整池子，自己判断。")
else:
    for it in hk_top:
        _render_card(it, "up")

st.markdown(f"**📋 港股 · 完整新股池（{len(hk_pool)}）**")
if hk_pool:
    for it in hk_pool:
        review = it.get("review") or {}
        sug = review.get('suggestion','-')
        with st.expander(f"{it.get('name')} —— {sug}"):
            st.markdown(f"**👍 看点**：{'、'.join(review.get('pros') or []) or '—'}")
            st.markdown(f"**⚠️ 风险**：{'、'.join(review.get('cons') or []) or '—'}")
            st.markdown(f"**为啥这么建议**：{review.get('rationale','—')}")
            for n in it.get("news") or []:
                st.markdown(f"- [{n.get('title','')}]({n.get('link','#')})")
else:
    st.caption("当前没抓到港股新股（akshare 接口可能临时不可用，可稍后刷新）。")

st.markdown("---")

# ============= A 股部分 =============
st.subheader("🇨🇳 A 股新股")

st.markdown("**🚀 A 股 · AI 建议积极申购**")
if not a_top:
    st.info("当前 A 股推荐池里 AI 没标『积极申购』。")
else:
    for it in a_top:
        _render_card(it, "up")

st.markdown(f"**📋 A 股 · 完整新股池（{len(a_pool)}）**")
if a_pool:
    for it in a_pool:
        review = it.get("review") or {}
        sug = review.get('suggestion','-')
        with st.expander(f"{it.get('name')} —— {sug}"):
            st.markdown(f"**👍 看点**：{'、'.join(review.get('pros') or []) or '—'}")
            st.markdown(f"**⚠️ 风险**：{'、'.join(review.get('cons') or []) or '—'}")
            st.markdown(f"**为啥这么建议**：{review.get('rationale','—')}")
            for n in it.get("news") or []:
                st.markdown(f"- [{n.get('title','')}]({n.get('link','#')})")
else:
    st.caption("当前没抓到 A 股新股。")

# ============= 热点新闻 =============
if hot_news:
    st.markdown("---")
    st.subheader("🔥 打新相关热点")
    for n in hot_news:
        st.markdown(
            f"- [{n.get('title','')}]({n.get('link','#')})  \n"
            f"  <span style='color:#8B949E;font-size:12px'>{n.get('source','')} · {n.get('published','')}</span>",
            unsafe_allow_html=True,
        )
