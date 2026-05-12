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
            "model_fast": settings.openai_model_fast,
            "model_deep": settings.openai_model_deep,
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

        # 用 fast 模型测：便宜、足够验证连通性
        import time
        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=settings.openai_model_fast,
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
    def _resolve_model(self, tier: str) -> str:
        """tier: "fast" | "deep"。"""
        if tier == "deep":
            return settings.openai_model_deep
        if tier == "fast":
            return settings.openai_model_fast
        return settings.openai_model

    def chat(self, system: str, user: str, *, json_mode: bool = False,
             temperature: float = 0.4, max_tokens: int = 1200,
             tier: str = "fast") -> str:
        """tier="fast" 用低价模型（日常聚合）；tier="deep" 用深度推理模型（关键决策）。"""
        if not self._client:
            return ""
        model = self._resolve_model(tier)
        try:
            kwargs: dict[str, Any] = dict(
                model=model,
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
            logger.info("LLM chat OK tier=%s model=%s", tier, model)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("LLM chat failed (tier=%s model=%s): %s", tier, model, e)
            return ""

    # ---------- 业务封装 ----------
    # tier 分级原则：
    #   - fast：信息聚合 / 总结（板块新闻、Trump 日常分析），调用次数多
    #   - deep：可执行的买卖决策（追踪股操作建议、新股 / 打新申购建议），调用次数少但要准
    def summarize_sector(self, sector: str, news_titles: list[str]) -> str:
        if not self._client or not news_titles:
            return self._fallback_sector_summary(sector, news_titles)
        sys = (
            "你是个会聊天的股市观察员，用大白话给普通投资者讲板块最近发生了啥。"
            "2-4 句话讲清楚：最近这个板块在涨还是在跌，主要因为啥（用通俗例子和比喻），"
            "有啥需要注意的风险。语气要像朋友聊天，避免堆砌专业术语。"
        )
        usr = f"板块：{sector}\n最近相关新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:20])
        out = self.chat(sys, usr, max_tokens=500, tier="fast")
        return out or self._fallback_sector_summary(sector, news_titles)

    def analyze_trump_impact(self, news_titles: list[str]) -> str:
        if not self._client or not news_titles:
            return self._fallback_trump(news_titles)
        sys = (
            "你是个会用大白话讲宏观的策略师。基于特朗普最近的新闻，告诉普通投资者："
            "(1) 他最近在折腾啥；(2) 这事按常理走会怎么影响美股、A股、港股；"
            "(3) 哪些股票/板块要小心，哪些可能反而沾光。"
            "语气要像在饭桌上聊新闻，控制 300 字内。不要套用『核心事件/市场逻辑/影响/风险』这种生硬框架，"
            "直接讲故事讲透就行。"
        )
        usr = "新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:25])
        out = self.chat(sys, usr, max_tokens=900, tier="deep")
        return out or self._fallback_trump(news_titles)

    def extract_trump_events(self, news_items: list[dict]) -> list[dict]:
        """从新闻里抽出最近的特朗普事件，每个事件包含日期、标题、通俗解读、对市场的影响。

        返回结构化 JSON 列表，便于 UI 渲染成时间轴。
        """
        if not self._client or not news_items:
            return self._fallback_trump_events(news_items)
        # 给 LLM 紧凑的输入：标题 + 发布时间 + 链接索引
        compact = []
        for i, n in enumerate(news_items[:30]):
            compact.append(f"[{i}] {n.get('published','')[:10]} {n.get('title','')}")
        sys = (
            "你是个会用大白话讲新闻的财经编辑。任务：从下面这堆特朗普相关新闻里，"
            "整理出最近最重要的 5-8 个『事件』。"
            "每个事件要做到：1) 一句话标题；2) 用 1-2 句大白话告诉普通人这事是怎么回事（举例、打比方都行）；"
            "3) 给出对股市的『简明影响』（比如：『美股短期会震，受影响的是芯片股』）。"
            "严格输出 JSON："
            "{\"events\":[{\"date\":\"YYYY-MM-DD\",\"title\":\"...\",\"plain\":\"...\",\"impact\":\"...\",\"refs\":[新闻索引]}]}"
        )
        usr = "新闻列表：\n" + "\n".join(compact)
        raw = self.chat(sys, usr, json_mode=True, max_tokens=1500, tier="deep")
        try:
            data = json.loads(raw)
            events = data.get("events") or []
            # 把 refs 索引换成实际链接，方便 UI 渲染
            for ev in events:
                refs = ev.get("refs") or []
                ev["links"] = []
                for idx in refs:
                    try:
                        idx_int = int(idx)
                        if 0 <= idx_int < len(news_items):
                            n = news_items[idx_int]
                            ev["links"].append({"title": n.get("title",""), "url": n.get("link","")})
                    except Exception:
                        continue
                ev.pop("refs", None)
            return events
        except Exception as e:
            logger.warning("extract_trump_events parse failed: %s", e)
            return self._fallback_trump_events(news_items)

    def stock_outlook(self, name: str, recent_pct: float, news_titles: list[str],
                      ma_signal: str) -> dict:
        """返回 dict: {trend, rationale, suggestion}。涉及具体买卖决策，用 deep。"""
        if not self._client:
            return self._fallback_stock(name, recent_pct, news_titles, ma_signal)
        sys = (
            "你是个会跟普通散户聊天的股市观察员。基于近期涨跌、均线、新闻舆情，"
            "给出短期（1-2 周）的趋势判断和操作建议。"
            "rationale 和 suggestion 都用大白话，像朋友提醒：『最近热度起来了，可以拿着别动』、"
            "『回到 XX 元附近再考虑加点』这种。避免『建议持仓比例不超过 30%』这种生硬话。"
            "严格输出 JSON：{\"trend\":\"上行/震荡/下行\",\"rationale\":\"中文 1-2 句大白话\","
            "\"suggestion\":\"中文 1 句具体建议，能直接照做\"}。"
        )
        usr = (
            f"股票：{name}\n近 20 日累计涨跌幅：{recent_pct:.2f}%\n"
            f"均线信号：{ma_signal}\n"
            f"近期相关新闻：\n" + "\n".join(f"- {t}" for t in news_titles[:15])
        )
        raw = self.chat(sys, usr, json_mode=True, max_tokens=500, tier="deep")
        try:
            data = json.loads(raw)
            if all(k in data for k in ("trend", "rationale", "suggestion")):
                return data
        except Exception:
            pass
        return self._fallback_stock(name, recent_pct, news_titles, ma_signal)

    def ipo_review(self, ipo: dict) -> dict:
        """打新 / 新股推荐：用 deep，因为是申购决策。"""
        if not self._client:
            return self._fallback_ipo(ipo)
        sys = (
            "你是个会用大白话讲新股的研究员，专门给散户讲清楚要不要打新。"
            "结合行业前景、估值是不是太贵、基石投资者强不强、市场情绪好不好，"
            "用普通人听得懂的话讲。优势/劣势都用具体例子和比喻，避免堆术语。"
            "输出 JSON：{\"pros\":[\"优势1\",\"优势2\"],\"cons\":[\"劣势1\"],"
            "\"suggestion\":\"建议（积极申购/谨慎申购/观望/不建议）\",\"rationale\":\"中文 1-2 句大白话讲清楚为啥\"}。"
        )
        usr = "新股资料：\n" + json.dumps(ipo, ensure_ascii=False, indent=2)
        raw = self.chat(sys, usr, json_mode=True, max_tokens=600, tier="deep")
        try:
            data = json.loads(raw)
            data.setdefault("pros", [])
            data.setdefault("cons", [])
            data.setdefault("suggestion", "观望")
            data.setdefault("rationale", "")
            return data
        except Exception:
            return self._fallback_ipo(ipo)

    @staticmethod
    def _fallback_trump_events(news_items: list[dict]) -> list[dict]:
        events = []
        for n in news_items[:6]:
            events.append({
                "date": (n.get("published") or "")[:10],
                "title": n.get("title") or "未知事件",
                "plain": "（未配置 LLM，仅显示新闻标题，无法生成大白话解读）",
                "impact": "—",
                "links": [{"title": n.get("title",""), "url": n.get("link","")}],
            })
        return events

    # ---------- 启发式回退 ----------
    @staticmethod
    def _fallback_sector_summary(sector: str, titles: list[str]) -> str:
        if not titles:
            return f"还没抓到 {sector} 的最新新闻。一会儿再点刷新试试。"
        top = "；".join(t for t in titles[:3] if t)
        return f"{sector} 最近的看点：{top}。（提示：还没配 AI Key，这里只是拼了几条标题。）"

    @staticmethod
    def _fallback_trump(titles: list[str]) -> str:
        if not titles:
            return "还没抓到特朗普的相关新闻。"
        head = "；".join(t for t in titles[:3] if t)
        return (
            f"特朗普最近在干啥：{head}。\n\n"
            "简单理解：他要是搞关税/制裁，风险资产（股票、加密币）会震荡，避险资产（黄金、美债）会涨；"
            "他要是减税/松监管，美股估值会修复；"
            "他要是对中国科技下手，A 股 / 港股科技板块短期会抖。\n"
            "（提示：还没配 AI Key，没法给具体事件做大白话解读。）"
        )

    @staticmethod
    def _fallback_stock(name: str, recent_pct: float, titles: list[str], ma_signal: str) -> dict:
        if recent_pct > 8:
            trend = "上行"
            suggestion = "短期挺强，先拿着别动；想加仓等回到 5/20 日均线附近。"
        elif recent_pct < -8:
            trend = "下行"
            suggestion = "短期偏弱，先观望或者减一些，别急着抄底。"
        else:
            trend = "震荡"
            suggestion = "在区间里磨，等方向出来再动手。"
        rationale = f"近 20 天涨了 {recent_pct:.2f}%，均线信号：{ma_signal}。"
        if titles:
            rationale += f" 最近相关消息：{titles[0]}。"
        return {"trend": trend, "rationale": rationale, "suggestion": suggestion}

    @staticmethod
    def _fallback_ipo(ipo: dict) -> dict:
        return {
            "pros": ["—"],
            "cons": ["还没配 AI Key，没法做深度分析"],
            "suggestion": "观望",
            "rationale": f"还没配 AI Key，仅返回基础信息：{ipo.get('name', ipo.get('股票简称', ''))}",
        }


llm = LLMClient()
