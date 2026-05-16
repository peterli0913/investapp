"""模块 5：新股推荐。

聚合 A 股 / 港股新股池（akshare 多接口 + Google News 兜底），结合行业热点 + 板块景气度，
请 LLM 给出适合入手的标的。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.modules.ipo import _extract_hk_ipos_from_news
from app.services.llm_client import _extract_json, llm
from app.services.market_data import a_new_stock_calendar, hk_ipo_calendar
from app.services.news_feed import fetch_keywords, google_news_rss
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("reco")


def _extract_a_ipos_from_news() -> list[dict]:
    """A 股新股 fallback：从新闻 + LLM 提取。"""
    keywords = ["A股 新股 申购", "A股 IPO 申购日", "A股 打新", "A股 新股 上市"]
    news = fetch_keywords(keywords, lang="zh-CN", country="CN", per=4)
    if not news or not llm.available:
        return []
    titles_block = []
    for i, n in enumerate(news[:25]):
        pub = (n.published or "")[:10]
        titles_block.append(f"[{i}] {pub} {n.title}")
    sys = (
        "你是 A 股新股研究员。从新闻里提取最近可申购或刚上市的 A 股新股清单。每条："
        "name / symbol / industry / price / list_date / pe / highlight。"
        "严格输出 JSON：{\"ipos\":[{...}]}。"
    )
    usr = "新闻：\n" + "\n".join(titles_block)
    raw = llm.chat(sys, usr, json_mode=True, max_tokens=2000, tier="fast")
    data = _extract_json(raw) or {}
    ipos = data.get("ipos") if isinstance(data, dict) else []
    cleaned = []
    for it in ipos or []:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        cleaned.append({
            "股票简称": it.get("name"),
            "代码": it.get("symbol", ""),
            "行业": it.get("industry", "—"),
            "发行价": it.get("price", "—"),
            "上市日期": it.get("list_date", "—"),
            "市盈率": it.get("pe", "—"),
            "highlight": it.get("highlight", ""),
            "_source": "google_news+llm",
        })
    return cleaned


def _pool() -> list[dict]:
    """合并 A + 港新股池。akshare 拿不到时用新闻 + LLM 兜底。"""
    pool: list[dict] = []

    # A 股
    a = a_new_stock_calendar()
    a_rows: list[dict] = []
    if a is not None and not a.empty:
        for _, r in a.head(15).iterrows():
            row = r.to_dict()
            a_rows.append(row)
    if not a_rows:
        logger.info("_pool: A 股 akshare 无数据，走新闻 fallback")
        a_rows = _extract_a_ipos_from_news()
    for r in a_rows:
        r["市场"] = "A股"
        pool.append(r)

    # 港股
    hk = hk_ipo_calendar()
    hk_rows: list[dict] = []
    if hk is not None and not hk.empty:
        for _, r in hk.head(15).iterrows():
            hk_rows.append(r.to_dict())
    if not hk_rows:
        logger.info("_pool: 港股 akshare 无数据，走新闻 fallback")
        # 复用 ipo 模块的 fallback（同样的港股新股提取逻辑）
        fb = _extract_hk_ipos_from_news()
        # 映射回老字段名以便 _pick_name 命中
        for it in fb:
            hk_rows.append({
                "股票简称": it.get("name"),
                "代码": it.get("symbol", ""),
                "行业": it.get("industry", "—"),
                "招股价": it.get("price_range", "—"),
                "上市日期": it.get("list_date", "—"),
                "保荐人": it.get("sponsor", "—"),
                "募集资金": it.get("fund", "—"),
                "highlight": it.get("highlight", ""),
                "_source": "google_news+llm",
            })
    for r in hk_rows:
        r["市场"] = "港股"
        pool.append(r)

    logger.info("_pool: 共 %d 条（A股 %d / 港股 %d）",
                len(pool), len(a_rows), len(hk_rows))
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
