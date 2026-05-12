"""设置 / 自选股管理。"""
from __future__ import annotations

import streamlit as st

from app.storage.db import add_watchlist, get_watchlist, remove_watchlist
from app.ui_common import bootstrap_once, hero, inject_theme
from app.utils.config import settings

bootstrap_once()
inject_theme()
hero("⚙️ 设置 / 自选股", "管理热门股票追踪的目标列表，以及查看运行配置。")

st.subheader("自选股管理")
wl = get_watchlist()
if wl:
    for w in wl:
        c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
        c1.write(f"**{w['name']}**")
        c2.write(w["symbol"])
        c3.write(w["market"].upper())
        if c4.button("移除", key=f"rm_{w['symbol']}"):
            remove_watchlist(w["symbol"])
            st.rerun()
else:
    st.info("自选股为空，请在下方添加。")

st.markdown("---")
st.subheader("添加自选股")
with st.form("add_watchlist", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("股票名称", placeholder="如：胜宏科技")
    symbol = c2.text_input("代码", placeholder="A股：002613；港股：09992；美股：AAPL")
    market = c3.selectbox("市场", ["a", "hk", "us"], format_func=lambda x: {"a":"A股","hk":"港股","us":"美股"}[x])
    submitted = st.form_submit_button("添加")
    if submitted:
        if not name or not symbol:
            st.error("名称和代码不能为空。")
        else:
            add_watchlist(symbol.strip(), name.strip(), market)
            st.success(f"已添加 {name} ({symbol})。")
            st.rerun()

st.markdown("---")
st.subheader("运行配置")
st.code(
    f"""
LLM 已启用      : {settings.llm_enabled}
OpenAI 模型     : {settings.openai_model}
OpenAI BaseURL  : {settings.openai_base_url}
每日刷新时间    : {settings.daily_update_hhmm} ({settings.timezone})
SQLite 路径     : {settings.db_path}
""".strip(),
    language="text",
)
st.caption("如需修改：编辑根目录下的 `.env` 文件，然后重启应用。")
