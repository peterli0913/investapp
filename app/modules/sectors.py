"""模块 1：火热板块动态。

针对 港股 / 美股 / A 股 三大市场，覆盖 AI 应用、芯片、存储、机器人、大消费、石油等板块。
聚合新闻 + 板块行情 + LLM 总结。
"""
from __future__ import annotations

from typing import Any

from app.services.llm_client import llm
from app.services.market_data import sector_concept_rank, sector_industry_rank
from app.services.news_feed import fetch_keywords
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("sectors")


SECTOR_KEYWORDS = {
    "AI应用": ["AI应用", "生成式AI", "AI Agent", "OpenAI", "大模型 应用"],
    "芯片": ["芯片", "半导体", "GPU", "AI芯片", "英伟达", "台积电"],
    "存储": ["存储芯片", "DRAM", "NAND", "HBM", "存储 涨价"],
    "机器人": ["人形机器人", "机器人", "特斯拉 机器人", "宇树科技"],
    "大消费": ["消费 复苏", "白酒", "新消费", "免税", "零售"],
    "石油": ["原油", "OPEC", "油价", "中东 局势"],
}

MARKETS = ["A股", "港股", "美股"]


def _lang_country_for_market(market: str) -> tuple[str, str]:
    if market == "美股":
        return "en-US", "US"
    if market == "港股":
        return "zh-HK", "HK"
    return "zh-CN", "CN"


def build_sector_report() -> dict[str, Any]:
    """聚合每个市场 × 每个板块的新闻 + 板块涨跌幅 + AI 总结。"""
    report: dict[str, Any] = {
        "updated_at": now_bj().isoformat(),
        "markets": {},
    }

    # A 股板块行情
    concept = sector_concept_rank()
    industry = sector_industry_rank()
    rank_map: dict[str, dict] = {}
    for df in (concept, industry):
        if df is None or df.empty:
            continue
        name_col = next((c for c in df.columns if "名称" in c or "板块" in c), df.columns[0])
        chg_col = next((c for c in df.columns if "涨跌幅" in c or "涨幅" in c), None)
        for _, row in df.iterrows():
            name = str(row[name_col])
            rank_map[name] = {
                "pct": float(row[chg_col]) if chg_col and chg_col in row and row[chg_col] == row[chg_col] else None,
            }

    for market in MARKETS:
        lang, country = _lang_country_for_market(market)
        market_data: dict[str, Any] = {}
        for sector, kws in SECTOR_KEYWORDS.items():
            news = fetch_keywords([f"{sector} {market}"] + kws, lang=lang, country=country, per=4)
            titles = [n.title for n in news if n.title]
            summary = llm.summarize_sector(f"{market} - {sector}", titles)

            # 行情匹配（仅 A 股有概念板块涨跌幅数据）
            pct = None
            if market == "A股":
                for k, v in rank_map.items():
                    if sector in k or k in sector:
                        pct = v.get("pct")
                        break

            market_data[sector] = {
                "pct": pct,
                "summary": summary,
                "news": [n.to_dict() for n in news[:10]],
            }
        report["markets"][market] = market_data

    save_snapshot("sectors", "default", report)
    logger.info("sector report built at %s", report["updated_at"])
    return report
