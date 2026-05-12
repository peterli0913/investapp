"""模块 1：火热板块动态。

针对 港股 / 美股 / A 股 三大市场，覆盖 AI 应用、芯片、存储、机器人、大消费、石油等板块。
聚合新闻 + 板块行情 + LLM 总结。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.services.llm_client import llm
from app.services.market_data import (
    crypto_quote, sector_concept_rank, sector_industry_rank, yf_quote,
)
from app.services.news_feed import fetch_keywords, fetch_market_headlines
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

# 美股板块代表 ETF（用 yfinance 拿 24h 涨跌幅）
US_SECTOR_TICKERS: dict[str, list[str]] = {
    "AI应用":  ["ARKW", "BOTZ", "ROBO"],        # 互联网/AI/机器人 ETF
    "芯片":    ["SOXX", "SMH"],                 # 半导体 ETF
    "存储":    ["SMH"],                          # 内存 / 存储归在半导体大类
    "机器人":  ["BOTZ", "ROBO"],                # 机器人 ETF
    "大消费":  ["XLY", "XLP"],                   # 可选消费 / 必选消费
    "石油":    ["XLE", "XOP"],                   # 能源 ETF
}

# 港股板块代表标的（恒生科技 / 恒生消费 / 恒生指数）
HK_SECTOR_TICKERS: dict[str, list[str]] = {
    "AI应用":  ["^HSTECH"],   # 恒生科技指数
    "芯片":    ["^HSTECH"],
    "存储":    ["^HSTECH"],
    "机器人":  ["^HSTECH"],
    "大消费":  ["^HSI"],       # 恒生指数（代表）
    "石油":    ["0883.HK"],   # 中海油
}

# 日股板块代表
JP_SECTOR_TICKERS: dict[str, list[str]] = {
    "AI应用":  ["^N225"],     # 日经指数（代表）
    "芯片":    ["8035.T"],    # 东京电子（半导体设备龙头）
    "存储":    ["6857.T"],    # Advantest
    "机器人":  ["6954.T"],    # Fanuc
    "大消费":  ["3382.T"],    # 7&i
    "石油":    ["1605.T"],    # INPEX
}

# 韩股板块代表
KR_SECTOR_TICKERS: dict[str, list[str]] = {
    "AI应用":  ["035420.KS"],  # 韩国 Naver
    "芯片":    ["005930.KS"],  # 三星电子
    "存储":    ["000660.KS"],  # SK Hynix
    "机器人":  ["005930.KS"],
    "大消费":  ["097950.KS"],  # CJ 第一制糖
    "石油":    ["096770.KS"],  # SK Innovation
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


def _sector_etf_tickers(market: str, sector: str) -> list[str]:
    """根据 (市场, 板块) 返回应该用 yfinance 拉行情的 ticker 列表。"""
    if market == "美股":
        return US_SECTOR_TICKERS.get(sector, [])
    if market == "港股":
        return HK_SECTOR_TICKERS.get(sector, [])
    if market == "日股":
        return JP_SECTOR_TICKERS.get(sector, [])
    if market == "韩股":
        return KR_SECTOR_TICKERS.get(sector, [])
    return []


def _process_one(market: str, sector: str, kws: list[str], rank_map: dict[str, dict],
                 tickers: list[str] | None = None) -> tuple[str, str, dict]:
    """处理单个 (市场, 板块) 的新闻 + LLM 总结 + 板块行情。可并行调用。

    tickers 仅加密币市场需要传入；其他市场会自动根据 (市场, 板块) 查 ETF 列表。
    """
    lang, country = _lang_country_for_market(market)
    news = fetch_keywords([f"{sector} {market}"] + kws, lang=lang, country=country, per=4)
    titles = [n.title for n in news if n.title]
    summary = llm.summarize_sector(f"{market} - {sector}", titles)

    pct = None
    extra: dict = {}

    if market == "A股":
        # A 股从 akshare 板块涨跌榜匹配
        for k, v in rank_map.items():
            if sector in k or k in sector:
                pct = v.get("pct")
                break
    elif market == "加密币" and tickers:
        # 加密币用 yfinance 拉 24h 涨跌幅
        quotes = []
        for t in tickers:
            q = crypto_quote(t)
            if q:
                quotes.append(q)
        if quotes:
            pct = sum(q["pct_24h"] for q in quotes) / len(quotes)
            extra["quotes"] = quotes
    else:
        # 美股 / 港股 / 日股 / 韩股 → 用代表 ETF / 指数的 yfinance 行情
        etf_tickers = _sector_etf_tickers(market, sector)
        if etf_tickers:
            quotes = []
            for t in etf_tickers:
                q = yf_quote(t)
                if q:
                    quotes.append(q)
            if quotes:
                pct = sum(q["pct_24h"] for q in quotes) / len(quotes)
                extra["quotes"] = quotes

    return market, sector, {
        "pct": pct,
        "summary": summary,
        "news": [n.to_dict() for n in news[:10]],
        **extra,
    }


MARKET_CODE = {
    "A股": "cn", "港股": "hk", "美股": "us", "日股": "jp", "韩股": "kr", "加密币": "crypto",
}


def build_sector_report() -> dict[str, Any]:
    """聚合每个市场 × 每个板块的新闻 + 板块涨跌幅 + AI 总结。

    36 个 (市场, 板块) 任务并行；同时各市场抓常驻 RSS 头条作为"市场要闻"。
    """
    report: dict[str, Any] = {
        "updated_at": now_bj().isoformat(),
        "markets": {market: {} for market in MARKETS},
        "headlines": {market: [] for market in MARKETS},
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

    # 同时启动：各市场常驻 RSS 头条 + (市场, 板块) 任务
    # 5 股市 × 6 板块 + 加密币 × 6 主题 = 36 个任务 + 6 个市场要闻
    tasks: list[tuple[str, str, list[str], list[str]]] = []
    for market in MARKETS:
        if market == "加密币":
            for topic, conf in CRYPTO_TOPICS.items():
                tasks.append((market, topic, conf["keywords"], conf.get("tickers", [])))
        else:
            for sector, kws in SECTOR_KEYWORDS.items():
                tasks.append((market, sector, kws, []))

    # max_workers 不要超过 14：DeepSeek 单账号也有并发限制
    with ThreadPoolExecutor(max_workers=14, thread_name_prefix="sector") as pool:
        # 板块任务
        sector_futures = [pool.submit(_process_one, m, s, kws, rank_map, tickers)
                          for m, s, kws, tickers in tasks]
        # 各市场要闻（常驻 RSS）
        headline_futures = {
            market: pool.submit(fetch_market_headlines, MARKET_CODE.get(market, "global"), 15)
            for market in MARKETS
        }

        for fut in as_completed(sector_futures):
            try:
                market, sector, data = fut.result()
                report["markets"][market][sector] = data
            except Exception as e:
                logger.warning("sector task failed: %s", e)

        for market, fut in headline_futures.items():
            try:
                items = fut.result()
                report["headlines"][market] = [n.to_dict() for n in items]
            except Exception as e:
                logger.warning("headlines for %s failed: %s", market, e)

    save_snapshot("sectors", "default", report)
    logger.info("sector report built at %s", report["updated_at"])
    return report
