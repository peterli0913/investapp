"""新闻聚合：基于多个 RSS 源 + Google News 关键词。

所有源都是公开的，不需要 token。抓取失败时返回空列表，不影响其他模块。
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable

import feedparser
import requests
from cachetools import TTLCache, cached

from app.utils.logger import get_logger
from app.utils.tz import BEIJING

logger = get_logger("news")

# 通用财经源（中英文混合）
DEFAULT_FEEDS: dict[str, list[str]] = {
    "global": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.bloomberg.com/feed/podcast/etf-report.xml",
        "https://www.ft.com/?format=rss",
    ],
    "cn": [
        "https://feed.sina.com.cn/api/roll/get?pageid=153&lid=2509&num=20&format=rss",  # 新浪财经
        "https://www.cls.cn/telegraph/rss",  # 财联社（如可用）
        "https://wallstreetcn.com/feeds/news/all",  # 华尔街见闻
    ],
    "hk": [
        "https://www.hkex.com.hk/-/media/HKEX-Market/Listing/Market-Misc/IPO/IPO-RSS/IPO_TC.xml",
    ],
    "us": [
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://www.marketwatch.com/rss/topstories",
    ],
}


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


@cached(cache=TTLCache(maxsize=128, ttl=600))
def fetch_feed(url: str, timeout: int = 10) -> list[NewsItem]:
    """抓单个 RSS。带 10 分钟内存缓存，避免重复请求。"""
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
    out: list[NewsItem] = []
    for u in urls:
        out.extend(fetch_feed(u))
    return out


def fetch_keywords(keywords: list[str], lang: str = "zh-CN", country: str = "CN", per: int = 8) -> list[NewsItem]:
    out: list[NewsItem] = []
    for kw in keywords:
        items = google_news_rss(kw, lang=lang, country=country)
        out.extend(items[:per])
    seen = set()
    dedup = []
    for it in out:
        if it.link in seen:
            continue
        seen.add(it.link)
        dedup.append(it)
    return dedup
