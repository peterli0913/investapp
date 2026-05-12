"""LLM 客户端：OpenAI 协议（兼容 OpenAI / DeepSeek / Moonshot 等）。

没有配置 API Key 时，所有方法都自动回退到启发式实现，
保证 app 没有外部 key 也能跑出有意义的内容。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("llm")


def _extract_json(raw: str) -> Any:
    """从 LLM 输出里提取 JSON。

    DeepSeek V4 Pro 思考模式可能输出 <think>...</think> 包裹的推理过程，或加 ```json ... ```
    code fence；我们把这些剥掉再 parse。
    """
    if not raw:
        return None
    text = raw.strip()
    # 1. 去掉 <think>...</think> 块
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    # 2. 去掉 markdown code fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    # 3. 直接尝试
    try:
        return json.loads(text)
    except Exception:
        pass
    # 4. 截取第一个 { 到最后一个 } 之间的内容
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except Exception:
            pass
    # 5. 截取第一个 [ 到最后一个 ] 之间的内容
    first = text.find("[")
    last = text.rfind("]")
    if first >= 0 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except Exception:
            pass
    return None


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

    def analyze_global_impact(self, news_titles: list[str]) -> str:
        """对国际局势 / 美国 / 中国相关新闻做综合分析。"""
        if not self._client or not news_titles:
            return self._fallback_trump(news_titles)
        sys = (
            "你是个会用大白话讲宏观的策略师。基于下面这堆国际新闻（含特朗普政策、美联储、"
            "中美关系、地缘冲突、央行决议、大宗商品等），告诉普通投资者："
            "(1) 最近最大的几件事是啥；(2) 这些事按常理会怎么搅动美股、A 股、港股、加密币；"
            "(3) 哪些板块要小心，哪些可能沾光。"
            "语气像饭桌上聊新闻，控制 350 字内。不要套生硬框架，直接讲故事讲透。"
        )
        usr = "新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:25])
        out = self.chat(sys, usr, max_tokens=1200, tier="deep")
        return out or self._fallback_trump(news_titles)

    # 保留旧名作为别名，避免上游代码引用断裂
    analyze_trump_impact = analyze_global_impact

    def extract_global_events(self, news_items: list[dict]) -> list[dict]:
        """从国际新闻里抽出最近最重要的事件，含类型标签。

        每个事件：date / title / category / plain（大白话解读）/ impact（市场影响）/ links。
        """
        if not self._client or not news_items:
            return self._fallback_global_events(news_items)

        # 给 LLM 紧凑的输入：标题 + 发布时间 + 索引
        compact = []
        for i, n in enumerate(news_items[:40]):
            pub = (n.get("published") or "")[:10]
            title = (n.get("title") or "")[:200]  # 限长，防止超 token
            compact.append(f"[{i}] {pub} {title}")

        sys = (
            "你是个会用大白话讲新闻的财经编辑。任务：从下面这堆国际新闻里，整理出最近最重要的"
            "5-10 个『大事件』。范围包括但不限于：特朗普政策、美联储动作、中美关系、地缘冲突、"
            "央行决议、能源价格、AI/科技监管等。\n"
            "每个事件包含：\n"
            "- date: 事件日期 YYYY-MM-DD\n"
            "- title: 一句话标题\n"
            "- category: 事件类型，从这几个里选一个：政治 / 经济 / 地缘 / 科技 / 能源 / 监管 / 央行 / 其它\n"
            "- plain: 用 1-2 句大白话告诉普通人这事怎么回事（用例子、比喻都行）\n"
            "- impact: 1 句话讲对股市/加密币的影响（比如『美股芯片股短期会震』）\n"
            "- refs: 关联新闻的索引列表（从输入的 [i] 编号里挑 1-3 个）\n\n"
            "严格输出 JSON：{\"events\":[{...},{...}]}。不要输出 markdown，不要解释，直接给 JSON。"
        )
        usr = "新闻列表：\n" + "\n".join(compact)

        # 第一次尝试：deep 模式 + 充足 max_tokens
        raw = self.chat(sys, usr, json_mode=True, max_tokens=3500, tier="deep")
        events = self._parse_events(raw, news_items)
        if events:
            return events

        # 重试一次：换 fast 模式 + 简化 prompt（绕过 deep 思考模式可能的 JSON 不规范）
        logger.info("extract_global_events: deep mode failed to parse, retrying with fast tier")
        sys2 = (
            "你是财经编辑。从新闻列表里挑 5-10 件重要的事，每件事用 JSON 表示："
            "{\"date\":\"YYYY-MM-DD\",\"title\":\"标题\",\"category\":\"政治/经济/地缘/科技/能源/监管/央行/其它中的一个\","
            "\"plain\":\"大白话 1-2 句\",\"impact\":\"市场影响 1 句\",\"refs\":[索引]}"
            "。最终输出：{\"events\":[...]}。"
        )
        raw2 = self.chat(sys2, usr, json_mode=True, max_tokens=2500, tier="fast")
        events2 = self._parse_events(raw2, news_items)
        if events2:
            return events2

        logger.warning("extract_global_events: both LLM attempts failed, raw1=%s raw2=%s",
                       (raw or "")[:300], (raw2 or "")[:300])
        return self._fallback_global_events(news_items)

    # 老接口别名（向后兼容）
    extract_trump_events = extract_global_events

    @staticmethod
    def _parse_events(raw: str, news_items: list[dict]) -> list[dict]:
        """把 LLM 返回的 raw 解析成 events list，并把 refs 索引换成实际链接。"""
        if not raw:
            return []
        data = _extract_json(raw)
        if not data:
            return []
        events = data.get("events") if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not events:
            return []

        cleaned: list[dict] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
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
            ev.setdefault("category", "其它")
            ev.setdefault("date", "")
            ev.setdefault("title", "未知事件")
            ev.setdefault("plain", "")
            ev.setdefault("impact", "—")
            cleaned.append(ev)
        return cleaned

    @staticmethod
    def _fallback_global_events(news_items: list[dict]) -> list[dict]:
        events = []
        for n in news_items[:8]:
            events.append({
                "date": (n.get("published") or "")[:10],
                "title": n.get("title") or "未知事件",
                "category": "其它",
                "plain": "（暂未生成 AI 解读，可能是 LLM 未配置 / 返回失败。这里直接展示新闻标题。）",
                "impact": "—",
                "links": [{"title": n.get("title",""), "url": n.get("link","")}],
            })
        return events

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

    # _fallback_global_events 已在上面定义，作为兜底实现

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
