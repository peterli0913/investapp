"""模块 2：TACO 动态——专门收集 Trump 新闻 + 股市方向影响分析。

TACO = "Trump Always Chickens Out"，金融圈对其反复政策的戏称。
我们聚合 Trump 相关新闻，并请 LLM 给出对美股 / A 股 / 港股的方向性影响。
"""
from __future__ import annotations

from app.services.llm_client import llm
from app.services.news_feed import fetch_keywords
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("taco")

TRUMP_KEYWORDS_EN = [
    "Trump", "Trump tariff", "Trump China", "Trump Fed", "Trump executive order",
    "Trump policy", "Truth Social Trump",
]
TRUMP_KEYWORDS_ZH = [
    "特朗普", "特朗普 关税", "特朗普 中国", "特朗普 政策", "特朗普 美股",
]


def build_taco_report() -> dict:
    en_news = fetch_keywords(TRUMP_KEYWORDS_EN, lang="en-US", country="US", per=6)
    zh_news = fetch_keywords(TRUMP_KEYWORDS_ZH, lang="zh-CN", country="CN", per=5)
    all_news = en_news + zh_news
    seen = set()
    dedup = []
    for n in all_news:
        if n.link in seen:
            continue
        seen.add(n.link)
        dedup.append(n)

    titles = [n.title for n in dedup if n.title]
    analysis = llm.analyze_trump_impact(titles)

    report = {
        "updated_at": now_bj().isoformat(),
        "analysis": analysis,
        "news": [n.to_dict() for n in dedup[:30]],
    }
    save_snapshot("taco", "default", report)
    return report
