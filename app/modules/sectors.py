"""模块 1：火热板块动态。

针对 港股 / 美股 / A 股 三大市场，覆盖 AI 应用、芯片、存储、机器人、大消费、石油等板块。
聚合新闻 + 板块行情 + LLM 总结。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.services.llm_client import llm
from app.services.market_data import crypto_quote, sector_concept_rank, sector_industry_rank
from app.services.news_feed import fetch_keywords
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("sectors")


# 股票市场用这套板块
SECTOR_KEYWORDS = {
    "AI应用": ["AI应用", "生成式AI", "AI Agent", "OpenAI", "大模型 应用"],
    "芯片": ["芯片", "半导体", "GPU", "AI芯片", "英伟达", "台积电"],
    "存储": ["存储芯片", "DRAM", "NAND", "HBM", "存储 涨价"],
    "机器人": ["人形机器人", "机器人", "特斯拉 机器人", "宇树科技"],
    "大消费": ["消费 复苏", "白酒", "新消费", "免税", "零售"],
    "石油": ["原油", "OPEC", "油价", "中东 局势"],
}

# 加密币市场用这套主题（按热门币种 / 赛道分组），值里多了 yfinance 行情符号
# 格式：主题 -> {"keywords": [...], "tickers": ["BTC-USD", ...]}
CRYPTO_TOPICS = {
    "比特币 BTC": {
        "keywords": ["Bitcoin", "BTC", "比特币", "Bitcoin ETF"],
        "tickers": ["BTC-USD"],
    },
    "以太坊 ETH": {
        "keywords": ["Ethereum", "ETH", "以太坊", "ETH ETF"],
        "tickers": ["ETH-USD"],
    },
    "主流公链": {
        "keywords": ["Solana", "SOL", "BNB", "Avalanche", "Polygon"],
        "tickers": ["SOL-USD", "BNB-USD", "AVAX-USD"],
    },
    "稳定币 / 监管": {
        "keywords": ["stablecoin", "USDT", "USDC", "稳定币", "SEC crypto"],
        "tickers": [],
    },
    "DeFi / RWA": {
        "keywords": ["DeFi", "RWA", "real world asset", "tokenization"],
        "tickers": [],
    },
    "Meme / NFT": {
        "keywords": ["Dogecoin", "Shiba", "PEPE", "meme coin", "NFT 市场"],
        "tickers": ["DOGE-USD"],
    },
}

# 6 大市场：5 个股票市场 + 加密币
MARKETS = ["A股", "港股", "美股", "日股", "韩股", "加密币"]


def _lang_country_for_market(market: str) -> tuple[str, str]:
    if market == "美股":
        return "en-US", "US"
    if market == "港股":
        return "zh-HK", "HK"
    if market == "日股":
        return "ja", "JP"
    if market == "韩股":
        return "ko", "KR"
    if market == "加密币":
        return "en-US", "US"   # 加密币新闻主要还是英文源最多
    return "zh-CN", "CN"


def _process_one(market: str, sector: str, kws: list[str], rank_map: dict[str, dict],
                 tickers: list[str] | None = None) -> tuple[str, str, dict]:
    """处理单个 (市场, 板块) 的新闻 + LLM 总结。可并行调用。

    tickers 仅加密币市场使用，传入相应 yfinance 符号拉行情。
    """
    lang, country = _lang_country_for_market(market)
    news = fetch_keywords([f"{sector} {market}"] + kws, lang=lang, country=country, per=4)
    titles = [n.title for n in news if n.title]
    summary = llm.summarize_sector(f"{market} - {sector}", titles)

    pct = None
    extra = {}
    if market == "A股":
        for k, v in rank_map.items():
            if sector in k or k in sector:
                pct = v.get("pct")
                break
    elif market == "加密币" and tickers:
        # 用第一只代表性 ticker 的 24h 涨跌幅当作"板块涨跌幅"
        quotes = []
        for t in tickers:
            q = crypto_quote(t)
            if q:
                quotes.append({"ticker": t, **q})
        if quotes:
            pct = sum(q["pct_24h"] for q in quotes) / len(quotes)
            extra["quotes"] = quotes

    return market, sector, {
        "pct": pct,
        "summary": summary,
        "news": [n.to_dict() for n in news[:10]],
        **extra,
    }


def build_sector_report() -> dict[str, Any]:
    """聚合每个市场 × 每个板块的新闻 + 板块涨跌幅 + AI 总结。

    优化：18 个 (市场, 板块) 任务并行（每个任务内部已经并行抓 RSS + 调 LLM）。
    """
    report: dict[str, Any] = {
        "updated_at": now_bj().isoformat(),
        "markets": {market: {} for market in MARKETS},
    }

    # A 股板块行情（一次性串行抓即可，akshare 不支持并发太多）
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

    # 全部 (市场, 板块) 任务并行
    # 5 股市 × 6 板块 + 加密币 × 6 主题 = 36 个任务
    tasks: list[tuple[str, str, list[str], list[str]]] = []
    for market in MARKETS:
        if market == "加密币":
            for topic, conf in CRYPTO_TOPICS.items():
                tasks.append((market, topic, conf["keywords"], conf.get("tickers", [])))
        else:
            for sector, kws in SECTOR_KEYWORDS.items():
                tasks.append((market, sector, kws, []))

    # max_workers 不要超过 12：DeepSeek 单账号也有并发限制，过高反而被限流
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="sector") as pool:
        futures = [pool.submit(_process_one, m, s, kws, rank_map, tickers)
                   for m, s, kws, tickers in tasks]
        for fut in as_completed(futures):
            try:
                market, sector, data = fut.result()
                report["markets"][market][sector] = data
            except Exception as e:
                logger.warning("sector task failed: %s", e)

    save_snapshot("sectors", "default", report)
    logger.info("sector report built at %s", report["updated_at"])
    return report
