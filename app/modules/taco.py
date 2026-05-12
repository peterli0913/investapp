"""模块 2：TACO 动态——专门收集 Trump 新闻 + 股市方向影响分析。

TACO = "Trump Always Chickens Out"，金融圈对其反复政策的戏称。
我们聚合 Trump 相关新闻，并请 LLM 给出对美股 / A 股 / 港股的方向性影响。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

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
    # 中英文新闻并行抓
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="taco") as pool:
        f_en = pool.submit(fetch_keywords, TRUMP_KEYWORDS_EN, "en-US", "US", 6)
        f_zh = pool.submit(fetch_keywords, TRUMP_KEYWORDS_ZH, "zh-CN", "CN", 5)
        en_news = f_en.result()
        zh_news = f_zh.result()
    all_news = en_news + zh_news
    seen = set()
    dedup = []
    for n in all_news:
        if n.link in seen:
            continue
        seen.add(n.link)
        dedup.append(n)

    titles = [n.title for n in dedup if n.title]
    news_dicts = [n.to_dict() for n in dedup[:30]]

    # 并行：影响分析（整体看法）+ 事件时间轴（具体事件）
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="taco-llm") as pool:
        f_analysis = pool.submit(llm.analyze_trump_impact, titles)
        f_events = pool.submit(llm.extract_trump_events, news_dicts)
        analysis = f_analysis.result()
        events = f_events.result()

    report = {
        "updated_at": now_bj().isoformat(),
        "analysis": analysis,
        "events": events,
        "news": news_dicts,
    }
    save_snapshot("taco", "default", report)
    return report
