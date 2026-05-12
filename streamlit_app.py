"""Streamlit Cloud / 本地运行的入口。

部署到 Streamlit Cloud 时，把这个文件指定为 "Main file path" 即可。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st

# ===== 关键：把 Streamlit Cloud 的 secrets 同步到 os.environ =====
# 必须在 import app.* 之前完成，因为 app.utils.config 是模块加载时读取环境变量的
def _bridge_secrets_to_env() -> None:
    try:
        secrets_obj = getattr(st, "secrets", None)
        if secrets_obj is None:
            return
        # st.secrets 行为类似 dict；保险起见用 try/except 包裹每一项
        for key in list(secrets_obj.keys()):
            try:
                value = secrets_obj[key]
                # 只处理标量字符串；嵌套结构跳过
                if isinstance(value, (str, int, float)) and key not in os.environ:
                    os.environ[key] = str(value)
            except Exception:
                continue
    except Exception:
        # 本地无 secrets.toml 时 st.secrets 抛 StreamlitSecretNotFoundError，正常忽略
        pass


_bridge_secrets_to_env()

st.set_page_config(
    page_title="炒股助手 · 信息收集与辅助决策",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.ui_common import bootstrap_once, inject_theme  # noqa: E402

bootstrap_once()
inject_theme()


def _page(path: str, title: str, icon: str):
    return st.Page(path, title=title, icon=icon)


pg = st.navigation(
    {
        "概览": [_page("app/pages/0_首页.py", "首页", "🏠")],
        "信息模块": [
            _page("app/pages/1_火热板块动态.py", "火热板块动态", "🔥"),
            _page("app/pages/2_TACO动态.py", "国际动态", "🌍"),
            _page("app/pages/3_热门股票追踪.py", "热门股票追踪", "📊"),
            _page("app/pages/4_港股打新.py", "港股打新", "🆕"),
            _page("app/pages/5_新股推荐.py", "新股推荐", "⭐"),
        ],
        "分析": [_page("app/pages/6_回测训练.py", "回测训练", "🧪")],
        "设置": [_page("app/pages/7_设置.py", "设置 / 自选股", "⚙️")],
    }
)
pg.run()
