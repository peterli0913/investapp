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
            "你是资深的市场策略分析师，正在为同业同事撰写一段板块快评。"
            "请用 4-6 句话讲清楚：\n"
            "1) 板块近期方向（上行 / 震荡 / 下行）以及主要驱动力；\n"
            "2) 核心催化剂（具体到公司、产品、政策事件、关键数据）；\n"
            "3) 估值或资金面状态（如有可议的 PE/PB、北向资金、ETF 申赎、龙头股表现）；\n"
            "4) 短期需关注的风险点（基本面 / 情绪 / 监管 / 海外联动）。\n"
            "可使用『预期差』、『估值修复』、『资金高低切换』、『景气度』等专业术语，"
            "每个术语首次出现时用一句话点明含义。语气专业、克制，避免口语化开场白和过多感叹号。"
        )
        usr = f"板块：{sector}\n最近相关新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:25])
        out = self.chat(sys, usr, max_tokens=900, tier="fast")
        return out or self._fallback_sector_summary(sector, news_titles)

    def analyze_global_impact(self, news_titles: list[str]) -> str:
        """对国际局势 / 美国 / 中国相关新闻做综合分析。"""
        if not self._client or not news_titles:
            return self._fallback_trump(news_titles)
        sys = (
            "你是宏观策略分析师，正在为同业同事梳理近期国际动态对市场的可能影响，写一段研报式简评。\n"
            "请围绕以下三块写 500-700 字，分段叙述：\n"
            "1) 关键事件梳理：列出最重要的 3-5 个新闻或政策事件，简要交代背景与关键细节。\n"
            "2) 传导逻辑：用清晰的因果链解释这些事件如何影响美股 / A 股 / H 股 / 加密币市场。"
            "例如『关税升级 → 输入性通胀预期上行 → 美联储降息路径推迟 → 美债收益率上行 → 美股估值承压』。\n"
            "3) 板块与资产含义：哪些板块或资产可能受益 / 受损，给出具体方向和理由（涉及具体板块 / 个股 / 商品时务必点名）。\n"
            "可使用『风险偏好』、『久期』、『风险溢价』、『流动性溢价』、『盈利预期』等术语，"
            "首次出现时附一句简短解释。保持研报笔触：专业、有结构、有数据感，但避免堆砌生硬框架词，"
            "也不要使用『各位朋友』、『大家好』之类的开场白。"
        )
        usr = "新闻标题：\n" + "\n".join(f"- {t}" for t in news_titles[:30])
        out = self.chat(sys, usr, max_tokens=2000, tier="deep")
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
            "你是财经研究员，正在为同业同事整理一份国际动态简报。从下面新闻里挑出"
            "最近 7-10 个具有市场含义的事件。\n\n"
            "每个事件包含：\n"
            "- date: 事件日期 YYYY-MM-DD\n"
            "- title: 简洁有信息量的一句话标题（避免标题党）\n"
            "- category: 事件类型，从以下里选：政治 / 经济 / 地缘 / 科技 / 能源 / 监管 / 央行 / 其它\n"
            "- plain: 2-4 句话讲清楚『发生了什么 + 关键细节 + 为什么重要』。"
            "请像研究员之间的简报：可以使用『鹰派表态』、『缩表节奏』、『出口管制清单』等术语，"
            "但要把事件本身的来龙去脉说清楚，让看到的人立刻能理解背景。\n"
            "- impact: 1-2 句对市场的影响。具体到资产 / 板块（点名是哪些），"
            "并说明传导路径（例如『关税预期升温 → 半导体设备股承压 → 利好国产替代标的』）。\n"
            "- refs: 关联新闻的索引列表（从输入的 [i] 编号里挑 1-3 个最相关的）\n\n"
            "严格输出 JSON：{\"events\":[{...},{...}]}。不要输出 markdown 或解释，直接给 JSON。"
        )
        usr = "新闻列表：\n" + "\n".join(compact)

        # 第一次尝试：deep 模式 + 充足 max_tokens
        raw = self.chat(sys, usr, json_mode=True, max_tokens=4000, tier="deep")
        events = self._parse_events(raw, news_items)
        if events:
            return events

        # 重试一次：换 fast 模式 + 简化 prompt（绕过 deep 思考模式可能的 JSON 不规范）
        logger.info("extract_global_events: deep mode failed to parse, retrying with fast tier")
        sys2 = (
            "你是财经研究员。从新闻列表里挑 7-10 件有市场含义的事，每件事用 JSON 表示："
            "{\"date\":\"YYYY-MM-DD\",\"title\":\"标题\",\"category\":\"政治/经济/地缘/科技/能源/监管/央行/其它中的一个\","
            "\"plain\":\"2-3 句研报式简报，介绍事件来龙去脉\","
            "\"impact\":\"1-2 句对具体板块/资产的影响及传导路径\",\"refs\":[索引]}"
            "。最终输出：{\"events\":[...]}。"
        )
        raw2 = self.chat(sys2, usr, json_mode=True, max_tokens=3500, tier="fast")
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
            "你是股票研究员，给同业同事简评一只标的的短期（1-2 周）前景。\n"
            "综合考虑：近期涨跌幅、均线 / 多因子信号、新闻舆情、所属板块景气度、资金流向。\n"
            "严格输出 JSON：\n"
            "- trend: '上行' / '震荡' / '下行'\n"
            "- rationale: 3-4 句话说明判断逻辑。可使用『资金流』、『板块联动』、『催化剂』、"
            "『超买/超卖』、『放量突破』等术语，要把核心理由说清楚。\n"
            "- suggestion: 1-2 句具体操作建议。可包含：建议仓位区间、关键支撑 / 压力位、"
            "止盈止损参考、加仓减仓的触发条件。语气平实专业，不口语化，不要使用『拿着别动』、"
            "『先观望』这种过分口语的表述。\n"
            "再次强调：严格输出 JSON 对象，键名英文，不要 markdown 包裹。"
        )
        usr = (
            f"股票：{name}\n近 20 日累计涨跌幅：{recent_pct:.2f}%\n"
            f"均线信号：{ma_signal}\n"
            f"近期相关新闻：\n" + "\n".join(f"- {t}" for t in news_titles[:15])
        )
        raw = self.chat(sys, usr, json_mode=True, max_tokens=800, tier="deep")
        data = _extract_json(raw)
        if isinstance(data, dict) and all(k in data for k in ("trend", "rationale", "suggestion")):
            return data
        return self._fallback_stock(name, recent_pct, news_titles, ma_signal)

    def ipo_review(self, ipo: dict) -> dict:
        """打新 / 新股推荐：用 deep，因为是申购决策。"""
        if not self._client:
            return self._fallback_ipo(ipo)
        sys = (
            "你是港股 / A 股新股研究员，撰写打新简评。\n"
            "结合行业前景、估值（PE / PB / PS 与可比公司对照）、基石投资者质量与覆盖率、"
            "保荐人过往业绩、市场情绪、绿鞋机制、发行结构（公开发售比例 / 配售比例）等维度。\n"
            "输出 JSON：\n"
            "- pros: 2-4 条优势。务必具体有信息量，例如：『基石投资者覆盖公开发售 60%』、"
            "『行业 PE 中枢 25 倍，本次发行估值 18 倍存在折价』。\n"
            "- cons: 1-3 条劣势 / 风险。例如：『同行业上市后破发率 70%』、『毛利率 3 年连续下滑』。\n"
            "- suggestion: '积极申购' / '谨慎申购' / '观望' / '不建议'\n"
            "- rationale: 3-4 句话讲清楚为什么给出该建议，可使用专业术语并简要点明含义。\n"
            "保持研究员笔触：专业、有数据感、避免口语化。再次强调严格输出 JSON。"
        )
        usr = "新股资料：\n" + json.dumps(ipo, ensure_ascii=False, indent=2)
        raw = self.chat(sys, usr, json_mode=True, max_tokens=900, tier="deep")
        data = _extract_json(raw)
        if isinstance(data, dict):
            data.setdefault("pros", [])
            data.setdefault("cons", [])
            data.setdefault("suggestion", "观望")
            data.setdefault("rationale", "")
            return data
        return self._fallback_ipo(ipo)

    # _fallback_global_events 已在上面定义，作为兜底实现

    # ---------- 启发式回退 ----------
    @staticmethod
    def _fallback_sector_summary(sector: str, titles: list[str]) -> str:
        if not titles:
            return f"{sector}：未抓取到最新相关新闻，建议稍后重试。"
        top = "；".join(t for t in titles[:3] if t)
        return (f"{sector} 近期信息聚合（未启用 AI 总结，以下为最新原始标题摘录）：\n{top}。\n"
                "如需获得带传导逻辑的研报式解读，请在『设置』中配置 LLM API Key。")

    @staticmethod
    def _fallback_trump(titles: list[str]) -> str:
        if not titles:
            return "暂未抓取到相关国际新闻，建议稍后重试或检查网络。"
        head = "\n".join(f"• {t}" for t in titles[:5] if t)
        return (
            "国际动态原始标题（未启用 AI 总结）：\n"
            f"{head}\n\n"
            "通用传导框架供参考：\n"
            "1) 关税 / 制裁升级：输入性通胀预期上行 → 利率路径下修延后 → 风险资产（美股、A 股、加密币）承压，"
            "黄金、美债等避险资产相对受益。\n"
            "2) 减税 / 监管放松：企业盈利预期改善 → 美股估值修复，周期与小盘股弹性更大。\n"
            "3) 对华科技限制：半导体设备、AI 链条短期波动加剧，国产替代相关 A 股板块可能阶段性走强。\n"
            "（提示：配置 LLM API Key 后，将自动生成针对当日具体事件的传导分析与板块映射。）"
        )

    @staticmethod
    def _fallback_stock(name: str, recent_pct: float, titles: list[str], ma_signal: str) -> dict:
        if recent_pct > 8:
            trend = "上行"
            suggestion = (
                "近期动量较强，建议维持持仓；若有加仓意愿，可观察回踩 5 日 / 20 日均线时分批介入，"
                "止损参考 20 日均线下方。"
            )
        elif recent_pct < -8:
            trend = "下行"
            suggestion = (
                "短期趋势偏弱，建议降低仓位或暂时观望；待价格站稳 20 日均线、且伴随放量企稳后再考虑介入。"
            )
        else:
            trend = "震荡"
            suggestion = (
                "标的处于区间整理阶段，建议高抛低吸或保持轻仓观察，等待方向选择信号（如均线多头排列 / 放量突破）。"
            )
        rationale = (
            f"近 20 个交易日累计涨跌幅 {recent_pct:.2f}%；均线信号：{ma_signal}。"
        )
        if titles:
            rationale += f" 近期相关消息聚焦：{titles[0]}。"
        return {"trend": trend, "rationale": rationale, "suggestion": suggestion}

    @staticmethod
    def _fallback_ipo(ipo: dict) -> dict:
        return {
            "pros": ["公开发行渠道明确（基础信息）"],
            "cons": ["未启用 AI，无法进行估值对标、基石质量、行业景气度等深度分析"],
            "suggestion": "观望",
            "rationale": (
                f"未配置 LLM API Key，仅返回新股基础信息："
                f"{ipo.get('name', ipo.get('股票简称', '—'))}。建议在『设置』中配置后再做申购决策。"
            ),
        }


llm = LLMClient()
