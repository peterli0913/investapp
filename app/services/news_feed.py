"""新闻聚合：基于多个 RSS 源 + Google News 关键词。

所有源都是公开的，不需要 token。抓取失败时返回空列表，不影响其他模块。
"""
from __future__ import annotations

import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable

import feedparser
import requests
from cachetools import TTLCache, cached

from app.utils.logger import get_logger
from app.utils.tz import BEIJING

logger = get_logger("news")

# 全局线程池，所有并行 HTTP 共享，避免每次 build_*_report 都开新池
_HTTP_POOL = ThreadPoolExecutor(max_workers=24, thread_name_prefix="rss")

# 常驻财经 RSS 源池（按市场分类），用于每个市场 tab 的"市场要闻"
MARKET_FEEDS: dict[str, list[str]] = {
    "global": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/marketsNews",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",       # CNBC Markets
        "https://www.ft.com/?format=rss",                              # FT
        "https://www.investing.com/rss/news_25.rss",                   # Investing.com 全球
        "https://seekingalpha.com/market_currents.xml",                # Seeking Alpha
        "https://www.economist.com/finance-and-economics/rss.xml",     # Economist
    ],
    "cn": [
        "https://feed.sina.com.cn/api/roll/get?pageid=153&lid=2509&num=20&format=rss",  # 新浪财经
        "https://wallstreetcn.com/feeds/news/all",                      # 华尔街见闻
        "https://www.cls.cn/telegraph/rss",                             # 财联社
        "https://www.yicai.com/feed/",                                  # 第一财经
        "https://feed.sina.com.cn/api/roll/get?pageid=384&lid=2671&num=20&format=rss",  # 新浪 A 股
        "http://www.cs.com.cn/xwzx/hg/yw/rss.xml",                      # 中证网宏观
    ],
    "us": [
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",        # CNBC Top News
        "https://www.cnbc.com/id/15839069/device/rss/rss.html",         # CNBC Tech
        "https://www.marketwatch.com/rss/topstories",                   # MarketWatch
        "https://www.marketwatch.com/rss/marketpulse",                  # MarketWatch Pulse
        "https://www.investing.com/rss/news_301.rss",                   # Investing US Stocks
        "https://feeds.bbci.co.uk/news/business/rss.xml",               # BBC Business
    ],
    "hk": [
        "https://www.hkex.com.hk/-/media/HKEX-Market/Listing/Market-Misc/IPO/IPO-RSS/IPO_TC.xml",  # 港交所 IPO
        "https://hk.finance.yahoo.com/news/rssindex",                   # 雅虎财经 香港
        "http://www.aastocks.com/sc/rss/all.aspx",                      # AAStocks 简中
        "https://www.investing.com/rss/news_75.rss",                    # Investing 港股
    ],
    "jp": [
        "https://www.japantimes.co.jp/feed/topstories/",                # Japan Times
        "https://asia.nikkei.com/rss/feed/nar",                          # Nikkei Asia
    ],
    "kr": [
        "https://en.yna.co.kr/RSS/finance.xml",                          # 韩联社英文
        "https://www.investing.com/rss/news_357.rss",                   # Investing 韩股
    ],
    "crypto": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",              # CoinDesk
        "https://cointelegraph.com/rss",                                 # Cointelegraph
        "https://decrypt.co/feed",                                       # Decrypt
        "https://cryptopanic.com/news/rss/",                             # CryptoPanic
    ],
    # 主题专项源（用于国际动态模块的常驻补充）
    "macro": [
        "https://www.federalreserve.gov/feeds/press_all.xml",            # 美联储官方
        "https://feeds.reuters.com/reuters/topNews",                     # Reuters Top
        "http://rss.cnn.com/rss/cnn_world.rss",                          # CNN World
        "https://www.aljazeera.com/xml/rss/all.xml",                     # Al Jazeera（中东视角）
    ],
}

# 兼容老名字
DEFAULT_FEEDS = MARKET_FEEDS


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: str  # ISO 字符串，北京时间
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _to_bj_iso(time_struct) -> str:
    try:
        if time_struct is None:
            return ""
        dt = datetime(*time_struct[:6])
        return dt.astimezone(BEIJING).isoformat()
    except Exception:
        return ""


@cached(cache=TTLCache(maxsize=256, ttl=1800))  # 30 分钟缓存
def fetch_feed(url: str, timeout: int = 6) -> list[NewsItem]:
    """抓单个 RSS。带 30 分钟内存缓存，避免重复请求。

    timeout 6 秒：宁可个别源失败也别拖累整体；缓存 30 分钟所以这里宁短勿长。
    """
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 StockAssistant/1.0"})
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as e:
        logger.warning("fetch_feed failed: %s -> %s", url, e)
        return []

    items: list[NewsItem] = []
    src = parsed.feed.get("title", url)
    for e in parsed.entries[:30]:
        items.append(
            NewsItem(
                title=str(e.get("title", "")).strip(),
                link=str(e.get("link", "")).strip(),
                source=src,
                published=_to_bj_iso(e.get("published_parsed") or e.get("updated_parsed")),
                summary=str(e.get("summary", ""))[:500],
            )
        )
    return items


def google_news_rss(query: str, lang: str = "zh-CN", country: str = "CN") -> list[NewsItem]:
    """Google News 关键词 RSS。"""
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"
    return fetch_feed(url)


def fetch_many(urls: Iterable[str]) -> list[NewsItem]:
    """并行抓多个 RSS。比串行快 5-10 倍。"""
    urls = list(urls)
    if not urls:
        return []
    futures = [_HTTP_POOL.submit(fetch_feed, u) for u in urls]
    out: list[NewsItem] = []
    for fut in as_completed(futures):
        try:
            out.extend(fut.result())
        except Exception as e:
            logger.warning("fetch_many task failed: %s", e)
    return out


def fetch_market_headlines(market_code: str, limit: int = 25,
                            *, include_global: bool = True) -> list[NewsItem]:
    """聚合某个市场的常驻 RSS 源头条。

    market_code 形如 'cn' / 'us' / 'hk' / 'jp' / 'kr' / 'crypto' / 'macro' / 'global'。
    include_global=True 时会自动并入 global 源，扩大覆盖。
    """
    feeds = list(MARKET_FEEDS.get(market_code, []))
    if include_global and market_code != "global":
        feeds.extend(MARKET_FEEDS.get("global", []))
    items = fetch_many(feeds)
    # 按发布时间倒序，新的在前
    items.sort(key=lambda n: n.published or "", reverse=True)
    # 去重
    seen = set()
    out = []
    for n in items:
        if not n.title or n.link in seen:
            continue
        seen.add(n.link)
        out.append(n)
        if len(out) >= limit:
            break
    return out


def fetch_keywords(keywords: list[str], lang: str = "zh-CN", country: str = "CN", per: int = 8,
                   *, also_country: list[str] | None = None) -> list[NewsItem]:
    """并行抓多个关键词的 Google News。

    also_country：除了主 country 外再补一个 fallback，扩大召回率。
    例如 中文场景 country='CN' + also_country=['HK', 'TW']，抓取中港台三地中文新闻。
    """
    if not keywords:
        return []

    countries = [(lang, country)]
    if also_country:
        for c in also_country:
            countries.append((lang, c))

    def _one(kw_country: tuple[str, tuple[str, str]]) -> list[NewsItem]:
        kw, (l, c) = kw_country
        items = google_news_rss(kw, lang=l, country=c)
        return items[:per]

    tasks = [(kw, lc) for kw in keywords for lc in countries]
    futures = [_HTTP_POOL.submit(_one, t) for t in tasks]
    out: list[NewsItem] = []
    for fut in as_completed(futures):
        try:
            out.extend(fut.result())
        except Exception as e:
            logger.warning("fetch_keywords task failed: %s", e)
    seen = set()
    dedup = []
    for it in out:
        if not it.link or it.link in seen:
            continue
        seen.add(it.link)
        dedup.append(it)
    return dedup
