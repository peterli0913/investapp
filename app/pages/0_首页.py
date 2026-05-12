"""首页。"""
from __future__ import annotations

import streamlit as st

from app.scheduler.jobs import get_next_run, run_all_manual
from app.storage.db import load_snapshot
from app.ui_common import bootstrap_once, fmt_bj_iso, hero, inject_theme
from app.utils.config import settings

bootstrap_once()
inject_theme()
hero("📈 炒股小助手",
     "帮你每天早上 6:30 把市场动态梳理好。看看板块在火什么、特朗普又在折腾啥、你关注的股表现如何、港股新股值不值得打。")


col_a, col_b, col_c = st.columns([2, 2, 2])
with col_a:
    st.metric("下次自动刷新", get_next_run())
with col_b:
    st.metric("LLM 状态", "已启用" if settings.llm_enabled else "启发式回退")
with col_c:
    if st.button("一键刷新全部模块", type="primary", use_container_width=True):
        with st.spinner("正在刷新全部模块（可能耗时数十秒，取决于网络与外部 API）…"):
            run_all_manual()
        st.success("已完成全量刷新")

st.markdown("---")

st.subheader("各模块最新更新时间")
modules = [
    ("sectors", "🔥 最近啥板块在火"),
    ("taco", "🇺🇸 特朗普动态"),
    ("tracked", "📊 我的关注股"),
    ("ipo", "🆕 港股打新"),
    ("recommendations", "⭐ 新股推荐"),
]
cols = st.columns(len(modules))
for i, (key, label) in enumerate(modules):
    _, updated_at = load_snapshot(key)
    cols[i].markdown(
        f"""
        <div class="card">
            <div class="title">{label}</div>
            <div class="meta">{fmt_bj_iso(updated_at)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(
    """
    ### 怎么用
    - 左边菜单点一下就能切换到不同模块。
    - 每个页面顶部都有『立即刷新』按钮，等不及自动刷新可以随时点。
    - **第一次用先到 *⚙️ 设置 / 自选股*** 看一下：检查 LLM 是否连通、要不要把『泡泡玛特』换成你别的关注股。
    - 想知道 AI 的判断准不准？去『🧪 回测训练』选一只股票跑一下，能看到过去一年这套策略的实际胜率。
    """
)
