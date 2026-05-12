"""新闻情绪打分。

零依赖：基于一份中英文金融语境的关键词表做加权求和。
LLM Key 存在时，可调用 LLM 做更精细的打分（每天 1 次预算友好）。

输出：score ∈ [-1, 1]，正向 / 负向 / 中性。
"""
from __future__ import annotations

import re
from typing import Iterable

POSITIVE = {
    # 中文
    "利好", "上涨", "突破", "反弹", "回升", "增长", "扩张", "盈利", "增持", "收购",
    "签约", "中标", "订单", "扩产", "提价", "回购", "分红", "超预期", "强势", "走高",
    "复苏", "降息",
    # 英文
    "beat", "beats", "surge", "rally", "rebound", "upgrade", "buyback",
    "growth", "expansion", "record high", "profit", "stronger", "outperform",
    "rate cut",
}

NEGATIVE = {
    # 中文
    "利空", "下跌", "暴跌", "跳水", "破位", "下行", "亏损", "减持", "退市", "退订",
    "诉讼", "调查", "处罚", "罚款", "降级", "下调", "缩减", "裁员", "违约", "停牌",
    "做空", "崩盘", "加息", "关税", "制裁", "禁令", "撤回", "失败",
    # 英文
    "miss", "misses", "tumble", "plunge", "downgrade", "lawsuit", "probe",
    "fine", "layoff", "default", "delist", "sanction", "tariff", "ban", "halt",
    "warn", "warning", "underperform", "rate hike", "recession",
}


def keyword_score(text: str) -> float:
    """简单关键词打分。"""
    if not text:
        return 0.0
    low = text.lower()
    pos = sum(1 for w in POSITIVE if w.lower() in low)
    neg = sum(1 for w in NEGATIVE if w.lower() in low)
    total = pos + neg
    if total == 0:
        return 0.0
    raw = (pos - neg) / total
    # 信号强度按命中数加权（命中 1 → 0.5 衰减，命中 ≥3 → 1）
    weight = min(1.0, total / 3)
    return float(raw * weight)


def headlines_sentiment(titles: Iterable[str]) -> float:
    titles = [t for t in titles if t]
    if not titles:
        return 0.0
    scores = [keyword_score(t) for t in titles]
    return float(sum(scores) / max(len(scores), 1))


def headlines_sentiment_llm(titles: list[str]) -> float:
    """可选 LLM 路径。失败 / 未配置时回退到关键词。"""
    from app.services.llm_client import llm
    if not titles:
        return 0.0
    if not llm.available:
        return headlines_sentiment(titles)
    try:
        prompt_sys = (
            "你是金融情绪分析模型。基于一组新闻标题，输出 JSON："
            "{\"sentiment\": -1 到 1 的浮点数, \"reason\": \"中文 1 句\"}。"
            "负数代表利空，正数代表利好。"
        )
        prompt_usr = "标题：\n" + "\n".join(f"- {t}" for t in titles[:30])
        raw = llm.chat(prompt_sys, prompt_usr, json_mode=True, max_tokens=200, temperature=0.1)
        import json
        data = json.loads(raw)
        v = float(data.get("sentiment", 0.0))
        return max(-1.0, min(1.0, v))
    except Exception:
        return headlines_sentiment(titles)
