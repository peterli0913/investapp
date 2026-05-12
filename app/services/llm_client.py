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

    # ---------- 自检 ----------
    def ping(self) -> dict:
        """主动发一次最小请求，把 key/base_url/model/响应/错误打回来。

        用于排查类似 DeepSeek `Authentication Fails (governor)` 这种
        「key 没被带上」的错误：通过完整诊断信息确认请求到底是怎么发的。
        """
        masked_key = (settings.openai_api_key[:6] + "..." + settings.openai_api_key[-4:]
                      if len(settings.openai_api_key) >= 12 else "(空)")
        info: dict = {
            "api_key_present": bool(settings.openai_api_key),
            "api_key_length": len(settings.openai_api_key),
            "api_key_preview": masked_key,
            "base_url": settings.openai_base_url,
            "model": settings.openai_model,
            "client_initialized": self._client is not None,
            "ok": False,
            "latency_ms": None,
            "reply": None,
            "error": None,
            "hint": None,
        }
        if not settings.openai_api_key:
            info["error"] = "OPENAI_API_KEY 未配置"
            info["hint"] = "在 .env 中填 OPENAI_API_KEY=sk-xxx 后重启 streamlit"
            return info
        if not self._client:
            info["error"] = "LLM client 未初始化（可能是 SDK 加载失败）"
            return info

        import time
        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "你是连通性测试助手。"},
                    {"role": "user", "content": "请用一个汉字回复：好"},
                ],
                max_tokens=10,
                temperature=0.0,
            )
            info["ok"] = True
            info["latency_ms"] = int((time.time() - t0) * 1000)
            info["reply"] = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            info["latency_ms"] = int((time.time() - t0) * 1000)
            err_str = str(e)
            info["error"] = err_str
            # 智能给提示
            low = err_str.lower()
            if "governor" in low or "authorization" in low:
                info["hint"] = (
                    "DeepSeek 的 `Authentication Fails (governor)` 意思是请求里没带 Authorization "
                    "header。请确认：(1) .env 中的 OPENAI_API_KEY 不为空且无多余空格/引号；"
                    "(2) 重启了 streamlit；(3) base_url 用 https://api.deepseek.com（不带 /v1 也行）。"
                )
            elif "401" in err_str or "invalid" in low and "key" in low:
                info["hint"] = "API key 无效或已被吊销。去 https://platform.deepseek.com/api_keys 重新创建。"
            elif "insufficient" in low or "balance" in low or "billing" in low:
                info["hint"] = "账户余额不足。DeepSeek 需要先到平台充值（最低 1 元/$1）。"
                info["hint"] += " 充值入口：https://platform.deepseek.com/top_up"
            elif "model" in low and ("not" in low or "unknown" in low):
                info["hint"] = "模型名不存在。DeepSeek 现役模型：deepseek-v4-flash / deepseek-v4-pro"
            elif "timeout" in low or "connection" in low:
                info["hint"] = "网络连不上。如果你在国外，DeepSeek 不限地区；如果在受限网络下，建议配代理或换 OpenAI。"
            else:
                info["hint"] = "把 error 字段完整发我，我帮你看具体是哪一步。"
        return info

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
