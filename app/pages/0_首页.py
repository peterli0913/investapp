"""首页。"""
from __future__ import annotations

import streamlit as st

from app.scheduler.jobs import get_next_run, run_all_manual
from app.storage.db import load_snapshot
from app.ui_common import bootstrap_once, fmt_bj_iso, hero, inject_theme
from app.utils.config import settings

bootstrap_once()
inject_theme()
hero("炒股助手 · 信息收集与辅助决策",
     "每天北京时间 06:30 自动刷新 · 五大模块覆盖板块 / TACO / 自选股 / 港股打新 / 新股推荐")


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
    ("sectors", "🔥 火热板块动态"),
    ("taco", "🇺🇸 TACO 动态"),
    ("tracked", "📊 热门股票追踪"),
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
    ### 使用说明
    - 左侧导航可切换各功能页面。
    - 每个页面右上角都有"立即刷新"按钮。
    - **首次使用强烈建议**：先到 *设置 / 自选股* 页面，确认初始三只股票，并选择是否填写 LLM API Key。
    - 回测训练页面提供你描述的 "用 1 年前预测、看 11 个月前真实走势" 的诊断工具。
    """
)
