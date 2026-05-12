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
LLM 已启用       : {settings.llm_enabled}
LLM BaseURL      : {settings.openai_base_url}
Fast 模型（日常）: {settings.openai_model_fast}
Deep 模型（决策）: {settings.openai_model_deep}
每日刷新时间     : {settings.daily_update_hhmm} ({settings.timezone})
SQLite 路径      : {settings.db_path}
""".strip(),
    language="text",
)
st.caption(
    "如需修改：编辑根目录下的 `.env` 文件，然后重启应用。"
    " 业务调用分级：板块新闻总结 / 情绪打分 → **Fast**；"
    "追踪股操作建议 / 港股打新 / 新股推荐 / TACO 影响 → **Deep**。"
)

st.markdown("---")
st.subheader("LLM API 连通性自检")
st.caption(
    "点击下方按钮会真实发一次最小请求。即使返回错误也会把 base_url / 模型 / "
    "原始 error 完整打出来，方便定位 DeepSeek 的 `Authentication Fails (governor)` 这类问题。"
)

if st.button("🔌 测试 LLM 连接", type="primary"):
    from app.services.llm_client import llm
    with st.spinner("发送测试请求中…"):
        info = llm.ping()

    if info["ok"]:
        st.success(f"✅ 连接成功！模型回复：「{info['reply']}」 · 耗时 {info['latency_ms']} ms")
    else:
        st.error(f"❌ 连接失败：{info.get('error') or '未知'}")
        if info.get("hint"):
            st.warning(f"💡 排查建议：{info['hint']}")

    # 一定要展示完整诊断信息
    diag = {k: v for k, v in info.items() if k != "hint"}
    st.json(diag)

st.markdown(
    """
    #### DeepSeek 常见错误对照
    | 错误 | 真实原因 | 解决 |
    |---|---|---|
    | `Authentication Fails (governor)` | 请求里没带 Authorization header | 检查 `.env` 中 `OPENAI_API_KEY` 是否为空 / 有多余空格引号 / 重启 streamlit |
    | `401 Authentication Fails` | key 无效或被吊销 | 去 <https://platform.deepseek.com/api_keys> 重新创建 |
    | `402 Insufficient Balance` | 账户余额不足 | 去 <https://platform.deepseek.com/top_up> 充值（最低 1 元） |
    | `Model not exist` | 模型名错 | 用 `deepseek-v4-flash` 或 `deepseek-v4-pro` |
    """
)
