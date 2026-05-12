"""模块 4：港股打新。

抓港交所/东方财富的港股新股日历，并请 LLM 做优劣势分析与申购建议。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.llm_client import llm
from app.services.market_data import hk_ipo_calendar
from app.services.news_feed import fetch_keywords
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("ipo")


def _normalize_row(row: dict) -> dict:
    """对齐字段名（akshare 不同版本字段名不一致）。"""
    mapping = {
        "股票简称": "name", "名称": "name", "公司": "name",
        "股票代码": "symbol", "代码": "symbol",
        "招股价": "price_range", "发行价": "price_range", "招股价区间": "price_range",
        "上市日期": "list_date", "上市": "list_date",
        "招股截止日": "close_date", "公开发售截止日期": "close_date",
        "招股开始日": "open_date", "公开发售开始日期": "open_date",
        "募集资金": "fund", "募资": "fund",
        "保荐人": "sponsor", "联席保荐人": "sponsor",
        "行业": "industry", "所属行业": "industry",
    }
    out = {}
    for k, v in row.items():
        key = mapping.get(k, k)
        out[key] = v
    return out


def build_ipo_report(max_items: int = 8) -> dict:
    df = hk_ipo_calendar()
    rows: list[dict] = []
    if df is not None and not df.empty:
        for _, r in df.head(max_items).iterrows():
            rows.append(_normalize_row(r.to_dict()))

    def _one(ipo: dict) -> dict:
        name = ipo.get("name") or ipo.get("公司") or "新股"
        news = fetch_keywords([f"{name} 港股 招股", f"{name} IPO"], lang="zh-CN", country="CN", per=3)
        ipo_with_news = dict(ipo)
        ipo_with_news["news"] = [n.to_dict() for n in news[:5]]
        ipo_with_news["review"] = llm.ipo_review(ipo)
        return ipo_with_news

    enriched: list[dict] = []
    if rows:
        with ThreadPoolExecutor(max_workers=min(8, len(rows)), thread_name_prefix="ipo") as pool:
            futures = [pool.submit(_one, ipo) for ipo in rows]
            for fut in as_completed(futures):
                try:
                    enriched.append(fut.result())
                except Exception as e:
                    logger.warning("ipo task failed: %s", e)

    report = {"updated_at": now_bj().isoformat(), "items": enriched}
    save_snapshot("ipo", "default", report)
    return report
