"""模块 4：港股打新。

数据源策略（双轨）：
    A. akshare 多个接口轮询（东方财富 / 新浪 / 旧版）
    B. 失败或返回空时回退：用 Google News 抓 "港股 招股 / 港股 IPO" 等关键词，
       再用 LLM 从新闻里抽出结构化新股清单（标题/招股价/上市日/行业等）

并行送 AI 出申购建议。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.llm_client import _extract_json, llm
from app.services.market_data import hk_ipo_calendar
from app.services.news_feed import fetch_keywords, fetch_market_headlines
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


def _extract_hk_ipos_from_news() -> list[dict]:
    """fallback: 从 Google News + 港交所 + AAStocks + 雅虎财经香港 抓港股招股新闻，
    让 LLM 提结构化数据。

    返回与 _normalize_row 同样字段（name / price_range / list_date / industry / sponsor / fund）。
    """
    keywords = [
        "港股 招股", "港股 IPO 招股", "港股 公开发售", "Hong Kong IPO 招股",
        "港股 新股 上市", "港股 招股 截止", "港股 招股 基石",
        "港交所 上市聆讯",  # 补充：上市聆讯阶段也算潜在新股
    ]
    # 三路并行：Google News 关键词 + 港交所 RSS + 香港财经 RSS
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ipo-fetch") as p:
        f1 = p.submit(fetch_keywords, keywords, "zh-CN", "CN", 4)
        f2 = p.submit(fetch_market_headlines, "hk", 25, False)
        news_kw = f1.result()
        news_hk = f2.result()
    news = news_kw + news_hk
    # 去重
    seen = set()
    dedup = []
    for n in news:
        if not n.link or n.link in seen:
            continue
        seen.add(n.link)
        dedup.append(n)
    news = dedup
    if not news:
        logger.warning("ipo fallback: 无招股相关新闻抓到")
        return []

    # 未配置 LLM 时也提供基础信息（每条新闻包装成一个"虚拟新股"，让用户至少能看到原始新闻）
    if not llm.available:
        logger.info("ipo fallback: LLM 未配置，把抓到的新闻包装成基础卡片返回")
        out = []
        for n in news[:10]:
            out.append({
                "name": (n.title or "未知")[:50],
                "symbol": "",
                "industry": "—",
                "price_range": "—",
                "list_date": (n.published or "")[:10] or "—",
                "sponsor": "—",
                "fund": "—",
                "highlight": "",
                "_source": "news_only(no_llm)",
                "_raw_news": {"title": n.title, "link": n.link, "source": n.source},
            })
        return out

    # 让 LLM 从新闻里提取结构化清单
    titles_block = []
    for i, n in enumerate(news[:25]):
        pub = (n.published or "")[:10]
        titles_block.append(f"[{i}] {pub} {n.title}")

    sys = (
        "你是港股新股研究员。从下面这堆港股招股相关新闻中，提取出最近正在招股或即将上市的『新股清单』。"
        "只列出新闻明确提到的、真实存在的港股 IPO 项目。每条新股包括：\n"
        "- name: 公司名称（中文）\n"
        "- symbol: 港股代码（如已知；不知道填空字符串）\n"
        "- industry: 所属行业\n"
        "- price_range: 招股价区间（如已知）\n"
        "- list_date: 预计上市日期（如已知）YYYY-MM-DD\n"
        "- sponsor: 保荐人（如已知）\n"
        "- fund: 募资规模（如已知）\n"
        "- highlight: 1-2 句核心看点（基石投资者、行业地位、特殊安排等）\n"
        "严格输出 JSON：{\"ipos\":[{...}]}。如果没有合适的，输出 {\"ipos\":[]}。"
    )
    usr = "招股相关新闻：\n" + "\n".join(titles_block)
    raw = llm.chat(sys, usr, json_mode=True, max_tokens=2500, tier="fast")
    data = _extract_json(raw) or {}
    ipos = data.get("ipos") if isinstance(data, dict) else []
    cleaned: list[dict] = []
    for ipo in ipos or []:
        if not isinstance(ipo, dict) or not ipo.get("name"):
            continue
        cleaned.append({
            "name": ipo.get("name"),
            "symbol": ipo.get("symbol", ""),
            "industry": ipo.get("industry", "—"),
            "price_range": ipo.get("price_range", "—"),
            "list_date": ipo.get("list_date", "—"),
            "sponsor": ipo.get("sponsor", "—"),
            "fund": ipo.get("fund", "—"),
            "highlight": ipo.get("highlight", ""),
            "_source": "google_news+llm",
        })
    logger.info("ipo fallback: 从新闻 LLM 提取出 %d 条新股", len(cleaned))
    return cleaned


def build_ipo_report(max_items: int = 10) -> dict:
    df = hk_ipo_calendar()
    rows: list[dict] = []
    data_source = ""

    if df is not None and not df.empty:
        for _, r in df.head(max_items).iterrows():
            rows.append(_normalize_row(r.to_dict()))
        data_source = "akshare"
        logger.info("build_ipo_report: akshare 返回 %d 条新股", len(rows))

    # akshare 没数据 → 用新闻 + LLM 兜底
    if not rows:
        logger.info("build_ipo_report: akshare 无数据，使用新闻 + LLM 兜底")
        rows = _extract_hk_ipos_from_news()
        if rows:
            data_source = "google_news+llm"

    def _one(ipo: dict) -> dict:
        name = ipo.get("name") or ipo.get("公司") or "新股"
        news = fetch_keywords([f"{name} 港股 招股", f"{name} IPO"],
                              lang="zh-CN", country="CN", per=3)
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

    report = {
        "updated_at": now_bj().isoformat(),
        "items": enriched,
        "data_source": data_source or "none",
        "total": len(enriched),
    }
    save_snapshot("ipo", "default", report)
    logger.info("build_ipo_report done: source=%s total=%d", data_source, len(enriched))
    return report
