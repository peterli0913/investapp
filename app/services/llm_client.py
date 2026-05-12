"""LLM 客户端：OpenAI 协议（兼容 OpenAI / DeepSeek / Moonshot 等）。

没有配置 API Key 时，所有方法都自动回退到启发式实现，
保证 app 没有外部 key 也能跑出有意义的内容。
"""
from __future__ import annotations

import json
from typing import Any

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("llm")


class LLMClient:
    def __init__(self):
        self._client = None
        if settings.llm_enabled:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )
                logger.info("LLM client ready: %s @ %s", settings.openai_model, settings.openai_base_url)
            except Exception as e:
                logger.warning("LLM init failed, falling back to heuristics: %s", e)
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    # ---------- 通用调用 ----------
    def chat(self, system: str, user: str, *, json_mode: bool = False,
             temperature: float = 0.4, max_tokens: int = 1200) -> str:
        if not self._client:
            return ""
        try:
            kwargs: dict[str, Any] = dict(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = self._client.chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("LLM chat failed: %s", e)
            return ""

    # ---------- 业务封装 ----------
    def summarize_sector(self, sector: str, news_titles: list[str]) -> str:
        if not self._client or not news_titles:
            return self._fallback_sector_summary(sector, news_titles)
        sys = "你是资深的中文证券分析师，请用专业、克制的语气总结板块动态，2-4 句话，突出方向、催化剂、风险。"
        usr = f"板块：{sector}\n最近相关新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:20])
        out = self.chat(sys, usr, max_tokens=500)
        return out or self._fallback_sector_summary(sector, news_titles)

    def analyze_trump_impact(self, news_titles: list[str]) -> str:
        if not self._client or not news_titles:
            return self._fallback_trump(news_titles)
        sys = "你是宏观策略分析师。基于特朗普相关新闻，分析对美股、A股、港股的方向性影响。结构：核心事件、市场逻辑、对各市场短期影响、需关注的风险。语气克制，控制在 250 字内。"
        usr = "新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:25])
        out = self.chat(sys, usr, max_tokens=600)
        return out or self._fallback_trump(news_titles)

    def stock_outlook(self, name: str, recent_pct: float, news_titles: list[str],
                      ma_signal: str) -> dict:
        """返回 dict: {trend, rationale, suggestion}。"""
        if not self._client:
            return self._fallback_stock(name, recent_pct, news_titles, ma_signal)
        sys = (
            "你是中国市场的专业股票分析师。基于近期涨跌幅、均线信号、新闻舆情，"
            "给出短期（1-2 周）趋势判断与可执行操作建议。"
            "严格输出 JSON：{\"trend\":\"上行/震荡/下行\",\"rationale\":\"中文 1-2 句\",\"suggestion\":\"中文 1 句具体建议\"}。"
        )
        usr = (
            f"股票：{name}\n近 20 日累计涨跌幅：{recent_pct:.2f}%\n"
            f"均线信号：{ma_signal}\n"
            f"近期相关新闻：\n" + "\n".join(f"- {t}" for t in news_titles[:15])
        )
        raw = self.chat(sys, usr, json_mode=True, max_tokens=400)
        try:
            data = json.loads(raw)
            if all(k in data for k in ("trend", "rationale", "suggestion")):
                return data
        except Exception:
            pass
        return self._fallback_stock(name, recent_pct, news_titles, ma_signal)

    def ipo_review(self, ipo: dict) -> dict:
        if not self._client:
            return self._fallback_ipo(ipo)
        sys = (
            "你是港股新股研究员。结合行业、估值、基石投资者、市场情绪，"
            "输出 JSON：{\"pros\":[\"优势1\",\"优势2\"],\"cons\":[\"劣势1\"],"
            "\"suggestion\":\"建议（积极申购/谨慎申购/观望/不建议）\",\"rationale\":\"中文 1-2 句\"}。"
        )
        usr = "新股资料：\n" + json.dumps(ipo, ensure_ascii=False, indent=2)
        raw = self.chat(sys, usr, json_mode=True, max_tokens=500)
        try:
            data = json.loads(raw)
            data.setdefault("pros", [])
            data.setdefault("cons", [])
            data.setdefault("suggestion", "观望")
            data.setdefault("rationale", "")
            return data
        except Exception:
            return self._fallback_ipo(ipo)

    # ---------- 启发式回退 ----------
    @staticmethod
    def _fallback_sector_summary(sector: str, titles: list[str]) -> str:
        if not titles:
            return f"暂未获取到 {sector} 的最新新闻。请稍后手动刷新或检查网络。"
        top = "；".join(t for t in titles[:3] if t)
        return f"{sector} 近期关注点：{top}。（启发式总结：未配置 LLM Key，仅拼接最新标题。）"

    @staticmethod
    def _fallback_trump(titles: list[str]) -> str:
        if not titles:
            return "暂未获取到 Trump 相关新闻。"
        head = "；".join(t for t in titles[:3] if t)
        return (
            f"近期 Trump 相关动态：{head}。\n"
            "通用框架：关税/制裁言论 → 风险资产承压、避险走强；减税/放松监管 → 美股估值修复、"
            "对华科技限制升级 → A 股科技板块波动加剧。请结合具体新闻判断。"
        )

    @staticmethod
    def _fallback_stock(name: str, recent_pct: float, titles: list[str], ma_signal: str) -> dict:
        if recent_pct > 8:
            trend = "上行"
            suggestion = "短期偏强，可持有，回调至 5/20 日均线再考虑加仓。"
        elif recent_pct < -8:
            trend = "下行"
            suggestion = "短期偏弱，建议观望或减仓至轻仓。"
        else:
            trend = "震荡"
            suggestion = "区间操作，等待方向选择。"
        rationale = f"近 20 日涨跌幅 {recent_pct:.2f}%，均线信号：{ma_signal}。"
        if titles:
            rationale += f" 关注消息：{titles[0]}。"
        return {"trend": trend, "rationale": rationale, "suggestion": suggestion}

    @staticmethod
    def _fallback_ipo(ipo: dict) -> dict:
        return {
            "pros": ["公开发行渠道明确"],
            "cons": ["未配置 LLM，无法做深度分析"],
            "suggestion": "观望",
            "rationale": f"未配置 LLM，仅返回基础信息：{ipo.get('name', ipo.get('股票简称', ''))}",
        }


llm = LLMClient()
