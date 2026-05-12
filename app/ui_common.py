"""UI 公共组件。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from app.storage.db import init_db, load_snapshot
from app.scheduler.jobs import start_scheduler, get_next_run, run_module
from app.utils.config import settings
from app.utils.tz import fmt_bj, now_bj

THEME_PATH = Path(__file__).parent / "assets" / "theme.css"


def bootstrap_once() -> None:
    """每次页面渲染都会跑，但内部做了幂等：DB 只建一次，调度器只起一次。

    在 Streamlit Cloud 上即使调度器启动失败也不能阻塞 UI，所以每个子系统单独 try。
    """
    if "_booted" in st.session_state:
        return
    boot_errors: list[str] = []
    try:
        init_db()
    except Exception as e:
        boot_errors.append(f"init_db: {e}")
    try:
        start_scheduler()
    except Exception as e:
        boot_errors.append(f"start_scheduler: {e}")

    st.session_state._booted = True
    st.session_state._boot_errors = boot_errors
    if boot_errors:
        # 不抛错，但在 UI 上提示一次
        st.warning("启动时部分子系统初始化失败（不影响其他功能）：" + " | ".join(boot_errors))


def inject_theme() -> None:
    if THEME_PATH.exists():
        st.markdown(f"<style>{THEME_PATH.read_text(encoding='utf-8')}</style>",
                    unsafe_allow_html=True)


def hero(title: str, subtitle: str = "") -> None:
    inject_theme()
    st.markdown(
        f"""
        <div class="hero">
            <h1>{title}</h1>
            <div class="sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pct_html(v: float | None) -> str:
    if v is None:
        return '<span class="neutral">--</span>'
    klass = "up" if v > 0 else ("down" if v < 0 else "neutral")
    sign = "+" if v > 0 else ""
    return f'<span class="{klass}">{sign}{v:.2f}%</span>'


def render_refresh_bar(module_key: str, label: str) -> Any:
    """通用刷新条：显示上次更新时间 / 下次自动更新时间 / 手动刷新按钮。"""
    payload, updated_at = load_snapshot(module_key)
    cols = st.columns([2, 2, 2, 2])
    with cols[0]:
        st.markdown(f"**模块**：{label}")
    with cols[1]:
        st.markdown(f"**上次更新**：{fmt_bj_iso(updated_at) if updated_at else '无'}")
    with cols[2]:
        st.markdown(f"**下次自动**：{get_next_run()}")
    with cols[3]:
        clicked = st.button("立即刷新", key=f"refresh_{module_key}", use_container_width=True)
    if clicked:
        import time
        t0 = time.time()
        # 显示具体步骤说明，避免干瞪眼
        hint = {
            "sectors": "并行抓取 5 大股市 + 加密币共 36 个主题的新闻，AI 生成研报式板块综评（约 20-50 秒）",
            "taco": "并行抓取 30+ 国际关键词新闻，AI 输出宏观综评与事件时间轴（约 15-40 秒）",
            "tracked": "并行获取自选股行情 / 新闻 / 多因子信号 / AI 操作建议（约 10-30 秒）",
            "ipo": "拉取港股新股招股日历，AI 输出打新优劣势与申购建议（约 10-30 秒）",
            "recommendations": "聚合 A 股 + 港股新股池，AI 评级与基石覆盖分析（约 20-60 秒）",
        }.get(module_key, "")
        with st.spinner(f"正在刷新 {label} … {hint}"):
            new_payload = run_module(module_key)
        elapsed = time.time() - t0
        st.success(f"✅ {label} 已更新 · 耗时 {elapsed:.1f} 秒 · {fmt_bj()}")
        payload = new_payload or payload
        updated_at = now_bj().isoformat()
    if not settings.llm_enabled:
        st.info("提示：未配置 LLM API Key，AI 分析将走启发式回退。可在 `.env` 中填写 `OPENAI_API_KEY`。", icon="ℹ️")
    return payload, updated_at


def fmt_bj_iso(iso: str | None) -> str:
    if not iso:
        return "无"
    try:
        from datetime import datetime
        return fmt_bj(datetime.fromisoformat(iso))
    except Exception:
        return iso
