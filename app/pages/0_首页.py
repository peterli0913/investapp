"""首页。"""
from __future__ import annotations

import streamlit as st

from app.scheduler.jobs import get_next_run, run_all_manual
from app.storage.db import load_snapshot
from app.ui_common import bootstrap_once, fmt_bj_iso, hero, inject_theme
from app.utils.config import settings

bootstrap_once()
inject_theme()
hero("📈 投研日报 · 信息收集与辅助决策",
     "每日北京时间 06:30 自动生成五大模块简报：板块景气度、国际宏观动态、自选股操作建议、港股打新、新股推荐。可随时手动刷新。")


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
    ("sectors", "🔥 板块景气度"),
    ("taco", "🌍 国际动态"),
    ("tracked", "📊 自选股追踪"),
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
    - 左侧导航切换不同模块。每个模块均支持手动『立即刷新』，无需等待自动调度。
    - **首次使用**建议先进入 *⚙️ 设置 / 自选股*：测试 LLM 连通性、调整自选股列表。
    - **策略验证**：*🧪 回测训练* 提供 7 种策略横向对比与 Walk-Forward 样本外测试，
      并支持 "1 年前预测 → 11 个月前真实走势" 的样本外诊断。
    - **模型分级**：日常聚合（板块新闻、情绪打分）走 `deepseek-v4-flash`；
      关键决策（操作建议、申购建议、宏观分析）自动切换 `deepseek-v4-pro` 思考模式。
    """
)
