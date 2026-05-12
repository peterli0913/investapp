"""模块 2：国际动态 / 大事追踪。

不再只盯特朗普。范围扩展到：
    - 特朗普政策（关税 / 行政令 / 对华表态）
    - 美联储 + 欧央行 + 日本央行政策、利率决议
    - 中美关系、地缘冲突（俄乌、中东、台海）
    - 大宗商品（油价、黄金、铜、稀土）
    - AI / 科技监管
帮你掌握最新国际局势对股市的影响。

模块 key 仍叫 'taco' 以兼容老 DB / 缓存。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.services.llm_client import llm
from app.services.news_feed import fetch_keywords, fetch_market_headlines
from app.storage.db import save_snapshot
from app.utils.logger import get_logger
from app.utils.tz import now_bj

logger = get_logger("taco")

# 英文关键词（信息源多、质量高）
GLOBAL_KEYWORDS_EN = [
    # 特朗普政策
    "Trump tariff", "Trump China", "Trump executive order", "Trump Fed",
    # 美联储 + 各央行
    "Fed rate decision", "FOMC", "ECB rate", "BOJ rate", "PBOC",
    # 经济数据
    "US CPI", "US jobs report", "US PMI",
    # 中美关系
    "US China trade", "US China chips", "US China sanctions",
    # 地缘
    "Russia Ukraine", "Middle East conflict", "Taiwan Strait", "North Korea",
    # 大宗
    "OPEC production", "oil price", "gold price",
    # 科技 / AI
    "AI regulation", "chips export control",
]

# 中文关键词（国内视角）
GLOBAL_KEYWORDS_ZH = [
    "特朗普", "特朗普 关税", "特朗普 中国",
    "美联储 加息", "美联储 降息", "FOMC 决议",
    "中美 关系", "中美 贸易", "中美 科技",
    "俄乌", "中东 局势", "台海", "朝鲜",
    "OPEC", "油价", "黄金 价格",
    "央行 政策", "人民币 汇率",
]


def build_taco_report() -> dict:
    # 三路并行：英文关键词 + 中文关键词 + 常驻宏观/全球 RSS 源
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="taco-fetch") as pool:
        f_en = pool.submit(fetch_keywords, GLOBAL_KEYWORDS_EN, "en-US", "US", 4)
        f_zh = pool.submit(fetch_keywords, GLOBAL_KEYWORDS_ZH, "zh-CN", "CN", 4)
        f_macro = pool.submit(fetch_market_headlines, "macro", 25, True)
        en_news = f_en.result()
        zh_news = f_zh.result()
        macro_news = f_macro.result()
    all_news = en_news + zh_news + macro_news

    # 去重
    seen = set()
    dedup = []
    for n in all_news:
        if not n.link or n.link in seen:
            continue
        seen.add(n.link)
        dedup.append(n)

    # 按发布时间倒序（新的在前）
    dedup.sort(key=lambda n: n.published or "", reverse=True)

    titles = [n.title for n in dedup if n.title]
    news_dicts = [n.to_dict() for n in dedup[:40]]

    if not news_dicts:
        logger.warning("build_taco_report: 没抓到新闻，可能是 Google News RSS 临时不可达")

    # 并行：整体看法（analysis）+ 事件时间轴（events）
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="taco-llm") as pool:
        f_analysis = pool.submit(llm.analyze_global_impact, titles)
        f_events = pool.submit(llm.extract_global_events, news_dicts)
        try:
            analysis = f_analysis.result(timeout=180)
        except Exception as e:
            logger.warning("analyze_global_impact failed/timeout: %s", e)
            analysis = ""
        try:
            events = f_events.result(timeout=180)
        except Exception as e:
            logger.warning("extract_global_events failed/timeout: %s", e)
            events = []

    # 兜底：LLM 返回空也要给用户看到东西
    if not analysis:
        analysis = (llm._fallback_trump(titles)
                    if hasattr(llm, "_fallback_trump")
                    else "（AI 暂时没返回，可稍后再点刷新）")
    if not events:
        events = (llm._fallback_global_events(news_dicts)
                  if hasattr(llm, "_fallback_global_events")
                  else [])

    report = {
        "updated_at": now_bj().isoformat(),
        "analysis": analysis,
        "events": events,
        "news": news_dicts,
        "news_count": len(news_dicts),
    }
    save_snapshot("taco", "default", report)
    logger.info("taco report built at %s · news=%d · events=%d",
                report["updated_at"], len(news_dicts), len(events))
    return report
