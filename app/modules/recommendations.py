"""模块 5：新股推荐。

聚合 A 股 / 港股新股池，结合行业热点 + 板块景气度，请 LLM 给出适合入手的标的。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.llm_client import llm
from app.services.market_data import a_new_stock_calendar, hk_ipo_calendar
from app.services.news_feed import fetch_keywords, google_news_rss
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("reco")


def _pool() -> list[dict]:
    """合并 A + 港新股池。"""
    pool: list[dict] = []
    a = a_new_stock_calendar()
    if a is not None and not a.empty:
        for _, r in a.head(15).iterrows():
            row = r.to_dict()
            row["市场"] = "A股"
            pool.append(row)
    hk = hk_ipo_calendar()
    if hk is not None and not hk.empty:
        for _, r in hk.head(15).iterrows():
            row = r.to_dict()
            row["市场"] = "港股"
            pool.append(row)
    return pool


def _pick_name(row: dict) -> str:
    for k in ("股票简称", "name", "名称", "公司", "证券简称"):
        if k in row and row[k]:
            return str(row[k])
    return "新股"


def build_recommendation_report() -> dict:
    pool = _pool()

    def _one(row: dict) -> dict:
        name = _pick_name(row)
        news = google_news_rss(f"{name} 新股")[:4]
        review = llm.ipo_review(row)
        return {
            "market": row.get("市场", ""),
            "name": name,
            "raw": row,
            "news": [n.to_dict() for n in news],
            "review": review,
        }

    enriched: list[dict] = []
    if pool:
        with ThreadPoolExecutor(max_workers=min(10, len(pool)), thread_name_prefix="reco") as p:
            futures = [p.submit(_one, row) for row in pool]
            for fut in as_completed(futures):
                try:
                    enriched.append(fut.result())
                except Exception as e:
                    logger.warning("reco task failed: %s", e)

    # 简单"推荐"筛选：suggestion 含 "积极" 或 "申购"
    top = [e for e in enriched if any(k in (e["review"].get("suggestion") or "")
                                      for k in ("积极", "建议申购", "适合"))]

    # 行业热点
    hot_news = fetch_keywords(["新股 申购 推荐", "IPO 热门"], per=5)

    report = {
        "updated_at": now_bj().isoformat(),
        "pool": enriched,
        "top": top,
        "hot_news": [n.to_dict() for n in hot_news],
    }
    save_snapshot("recommendations", "default", report)
    return report
