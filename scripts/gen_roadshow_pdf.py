"""生成「港股 IPO NDR · 5/27 一日路演计划」PDF。

用法：
    python3 scripts/gen_roadshow_pdf.py

输出：/workspace/Roadshow_HK-IPO_2026-05-27_Beijing.pdf
"""
from __future__ import annotations

from pathlib import Path
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Roadshow_HK-IPO_2026-05-27_Beijing.pdf"

CSS_STYLE = r"""
@page {
    size: A4;
    margin: 18mm 16mm 22mm 16mm;

    @top-left {
        content: "港股 IPO · 北京 NDR · 2026-05-27";
        font-family: "WenQuanYi Micro Hei", "Droid Sans Fallback", sans-serif;
        font-size: 8pt;
        color: #8B949E;
    }
    @top-right {
        content: "CONFIDENTIAL";
        font-family: "Helvetica", sans-serif;
        font-size: 8pt;
        color: #E5B864;
        font-weight: 700;
        letter-spacing: 1.2pt;
    }
    @bottom-center {
        content: "投行 IR · Page " counter(page) " of " counter(pages);
        font-family: "WenQuanYi Micro Hei", sans-serif;
        font-size: 8pt;
        color: #8B949E;
    }
}

/* 封面页：去掉页眉页脚 */
@page cover {
    margin: 0;
    @top-left { content: ""; }
    @top-right { content: ""; }
    @bottom-center { content: ""; }
}

/* 全局 */
* { box-sizing: border-box; }

html, body {
    font-family: "WenQuanYi Micro Hei", "Droid Sans Fallback", "Helvetica Neue", sans-serif;
    color: #1A1F2E;
    font-size: 9.5pt;
    line-height: 1.6;
    margin: 0;
    padding: 0;
}

/* 封面 */
.cover {
    page: cover;
    page-break-after: always;
    background: linear-gradient(135deg, #0E1117 0%, #1A2332 100%);
    color: #E6EDF3;
    height: 297mm;
    width: 210mm;
    padding: 40mm 25mm;
    position: relative;
}
.cover::before {
    content: "";
    position: absolute;
    top: 25mm;
    left: 25mm;
    right: 25mm;
    height: 2px;
    background: linear-gradient(90deg, #E5B864 0%, transparent 100%);
}
.cover .conf-tag {
    color: #E5B864;
    font-size: 10pt;
    letter-spacing: 4pt;
    font-weight: 700;
    margin-top: 5mm;
}
.cover h1 {
    font-size: 36pt;
    font-weight: 700;
    letter-spacing: 1pt;
    line-height: 1.25;
    margin: 35mm 0 12mm 0;
    color: #FFFFFF;
}
.cover .subtitle {
    font-size: 14pt;
    color: #C9D4DF;
    margin-bottom: 60mm;
    line-height: 1.6;
}
.cover .deal-info {
    border-left: 3px solid #E5B864;
    padding: 4mm 8mm;
    margin-bottom: 18mm;
}
.cover .deal-info .row {
    margin: 3mm 0;
    font-size: 10.5pt;
}
.cover .deal-info .row .label {
    color: #8B949E;
    display: inline-block;
    width: 28mm;
}
.cover .deal-info .row .value {
    color: #FFFFFF;
    font-weight: 600;
}
.cover .footer-mark {
    position: absolute;
    bottom: 30mm;
    left: 25mm;
    right: 25mm;
    color: #6E7681;
    font-size: 8pt;
    letter-spacing: 1pt;
    border-top: 1px solid #2A2F3A;
    padding-top: 4mm;
}

/* 标题层级 */
h1 {
    font-size: 18pt;
    color: #0E1117;
    border-bottom: 3px solid #E5B864;
    padding-bottom: 4mm;
    margin: 0 0 6mm 0;
    page-break-after: avoid;
}
h2 {
    font-size: 13pt;
    color: #1A2332;
    margin: 8mm 0 3mm 0;
    padding-left: 3mm;
    border-left: 4px solid #E5B864;
    page-break-after: avoid;
}
h3 {
    font-size: 11pt;
    color: #2A3B52;
    margin: 5mm 0 2mm 0;
    page-break-after: avoid;
}
p { margin: 0 0 3mm 0; }

/* 章节标题前换页 */
.section {
    page-break-before: always;
}
.section:first-of-type {
    page-break-before: auto;
}

/* TOC */
.toc {
    page-break-after: always;
    padding-top: 10mm;
}
.toc h1 {
    border-bottom: 3px solid #E5B864;
}
.toc ol {
    list-style: none;
    padding: 0;
    margin: 8mm 0;
    counter-reset: chapter;
}
.toc ol li {
    counter-increment: chapter;
    padding: 3mm 0;
    border-bottom: 1px dotted #C9D4DF;
    font-size: 11pt;
}
.toc ol li::before {
    content: counter(chapter, decimal-leading-zero) "  ";
    color: #E5B864;
    font-weight: 700;
    margin-right: 3mm;
    font-family: Helvetica, sans-serif;
}

/* 表格 */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 3mm 0 4mm 0;
    font-size: 8.5pt;
}
table th {
    background: #1A2332;
    color: #E6EDF3;
    padding: 2.5mm 2mm;
    text-align: left;
    font-weight: 600;
    font-size: 8pt;
    letter-spacing: 0.3pt;
}
table td {
    padding: 2mm 2mm;
    border-bottom: 1px solid #E5E9EE;
    vertical-align: top;
}
table tr:nth-child(even) td {
    background: #F7F9FB;
}

/* 卡片 (Prep Card / Box) */
.card {
    border: 1px solid #D5DCE5;
    border-radius: 4px;
    padding: 4mm 5mm;
    margin: 3mm 0 5mm 0;
    background: #FFFFFF;
    page-break-inside: avoid;
}
.card.tier-1 {
    border-left: 4px solid #E74C3C;
}
.card.tier-2 {
    border-left: 4px solid #E5B864;
}
.card.tier-3 {
    border-left: 4px solid #8B949E;
}
.card .card-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 3mm;
    padding-bottom: 2mm;
    border-bottom: 1px solid #E5E9EE;
}
.card .card-title {
    font-size: 12pt;
    font-weight: 700;
    color: #0E1117;
}
.card .card-time {
    font-size: 9pt;
    color: #6E7681;
    font-family: Helvetica, monospace;
}
.card .card-tier {
    display: inline-block;
    background: #1A2332;
    color: #E5B864;
    font-size: 8pt;
    padding: 1mm 3mm;
    border-radius: 3px;
    font-weight: 600;
    letter-spacing: 0.5pt;
    margin-left: 2mm;
}
.card.tier-1 .card-tier { background: #E74C3C; color: #fff; }
.card.tier-2 .card-tier { background: #E5B864; color: #1A2332; }
.card.tier-3 .card-tier { background: #8B949E; color: #fff; }

.card-block { margin: 2.5mm 0; }
.card-block .block-label {
    color: #6E7681;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 0.6pt;
    text-transform: uppercase;
    margin-bottom: 1mm;
}
.card-block ol, .card-block ul {
    margin: 0 0 0 5mm;
    padding: 0;
}
.card-block li {
    margin: 1mm 0;
    font-size: 9pt;
}
.card-block .redline {
    background: #FFF5F4;
    border-left: 3px solid #E74C3C;
    padding: 2mm 3mm;
    font-size: 9pt;
}
.card-block .target {
    background: #F4F8F5;
    border-left: 3px solid #27AE60;
    padding: 2mm 3mm;
    font-size: 9pt;
}

/* 时间轴风格 */
.timeline {
    border-left: 2px solid #E5B864;
    padding-left: 6mm;
    margin: 4mm 0 6mm 4mm;
}
.timeline .item {
    margin-bottom: 5mm;
    position: relative;
    page-break-inside: avoid;
}
.timeline .item::before {
    content: "";
    width: 8px;
    height: 8px;
    background: #E5B864;
    border-radius: 50%;
    position: absolute;
    left: -10.3mm;
    top: 3mm;
}
.timeline .item.meeting::before {
    background: #E74C3C;
    width: 10px;
    height: 10px;
    left: -10.5mm;
}
.timeline .time {
    font-family: Helvetica, monospace;
    font-weight: 700;
    color: #0E1117;
    font-size: 10pt;
}
.timeline .label {
    margin-left: 4mm;
    color: #2A3B52;
    font-size: 9.5pt;
}
.timeline .item.meeting .label {
    font-weight: 700;
    color: #C0392B;
}
.timeline .sub {
    margin-top: 1mm;
    color: #6E7681;
    font-size: 8pt;
}

/* 警示 / 高亮块 */
.notice {
    background: linear-gradient(90deg, #FFF9E6 0%, #FFFEF7 100%);
    border-left: 4px solid #E5B864;
    padding: 3mm 5mm;
    margin: 4mm 0;
    font-size: 9pt;
    border-radius: 0 3px 3px 0;
    page-break-inside: avoid;
}
.notice strong {
    color: #B7791F;
}

.danger {
    background: #FFF5F4;
    border-left: 4px solid #E74C3C;
    padding: 3mm 5mm;
    margin: 3mm 0;
    font-size: 9pt;
    border-radius: 0 3px 3px 0;
}

/* Checklist */
.checklist {
    list-style: none;
    padding: 0;
    margin: 3mm 0 5mm 0;
}
.checklist li {
    padding: 2mm 0;
    border-bottom: 1px dashed #D5DCE5;
    display: flex;
    align-items: flex-start;
    font-size: 9pt;
}
.checklist li::before {
    content: "☐";
    margin-right: 3mm;
    color: #6E7681;
    font-size: 11pt;
    line-height: 1;
}

/* 代码 / 模板块 */
.code-block {
    background: #1A2332;
    color: #E6EDF3;
    padding: 4mm 5mm;
    border-radius: 3px;
    font-family: "Courier New", monospace;
    font-size: 8pt;
    line-height: 1.55;
    white-space: pre-wrap;
    page-break-inside: avoid;
    margin: 3mm 0;
}
.code-block .gold { color: #E5B864; }
.code-block .red { color: #FFA199; }
.code-block .green { color: #7DD389; }
.code-block .gray { color: #8B949E; }

/* 标签 */
.tag {
    display: inline-block;
    padding: 0.5mm 2mm;
    border-radius: 3px;
    font-size: 7.5pt;
    background: #EEF1F4;
    color: #2A3B52;
    margin-right: 1.5mm;
    font-weight: 600;
}
.tag.red { background: #FDECEA; color: #C0392B; }
.tag.gold { background: #FFF6E0; color: #B7791F; }
.tag.green { background: #E8F5EC; color: #1E7E34; }
.tag.gray { background: #EEF1F4; color: #6E7681; }
"""

# ============ HTML BODY ============
HTML_BODY = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>路演计划 · 港股 IPO · 2026-05-27 · 北京</title>
</head>
<body>

<!-- ====== 封面 ====== -->
<section class="cover">
  <div class="conf-tag">CONFIDENTIAL · INTERNAL ONLY</div>
  <h1>港股 IPO 路演计划<br/>Investor Roadshow Plan</h1>
  <div class="subtitle">
    NDR · 北京一日密集会议 · 投行 IR 团队执行版<br/>
    Beijing One-Day NDR · Internal Use Only
  </div>

  <div class="deal-info">
    <div class="row"><span class="label">Project</span> <span class="value">HK IPO NDR · Beijing Leg</span></div>
    <div class="row"><span class="label">Date</span> <span class="value">2026 / 05 / 27 (Wednesday)</span></div>
    <div class="row"><span class="label">Location</span> <span class="value">北京 · 5 场 1-on-1（金融街 / CBD / 海淀）</span></div>
    <div class="row"><span class="label">Team</span> <span class="value">Lead Banker · VP · Analyst</span></div>
    <div class="row"><span class="label">Standard</span> <span class="value">HKEx Quiet Period · Prospectus-bound</span></div>
  </div>

  <div class="footer-mark">
    Prepared by Banking IR Team · Distribution restricted to deal team + syndicate desk<br/>
    Materials governed by Prospectus &amp; legal sign-off &nbsp;|&nbsp; Strictly no Reg-FD-violating disclosure
  </div>
</section>

<!-- ====== 目录 ====== -->
<section class="toc">
  <h1>目录 · Table of Contents</h1>
  <ol>
    <li>核心摘要 · Executive Summary</li>
    <li>逐时行程 · Hour-by-Hour Schedule</li>
    <li>5 场会议简报 · Prep Cards</li>
    <li>出租车日历模板 · Taxi Calendar Invites</li>
    <li>港股 IPO 合规清单 · HK IPO Compliance Checklist</li>
    <li>反馈追踪与日报模板 · Feedback Tracker &amp; Daily Summary</li>
    <li>出发前质量校验 · Pre-departure Quality Checks</li>
  </ol>
</section>

<!-- ====== 1. 核心摘要 ====== -->
<section class="section">
  <h1>1 · 核心摘要 · Executive Summary</h1>

  <p>本路演计划面向 <strong>香港 IPO 招股阶段</strong> 的 5 场北京潜在投资人 1-on-1，
    覆盖 2 家 Tier-1 央企/险资 LP（中国诚通、新华资产）、2 家 Tier-2 战略客户（中国移动、小米）、
    1 家 Tier-3 行业基准对照（智谱 AI）。当日核心目标是从两家 Tier-1 处获取明确 IOI（Indication of Interest）
    区间与可接受锁定期，并为 Tier-2 / Tier-3 建立长期 follow-up 通道。</p>

  <h2>关键指标 · Key Metrics</h2>
  <table>
    <thead>
      <tr><th style="width:42%">指标</th><th>目标</th></tr>
    </thead>
    <tbody>
      <tr><td>会议总数</td><td>5 场（4 个时段 + 1 场战略晚场）</td></tr>
      <tr><td>Tier-1 覆盖</td><td>2 家：中国诚通 / 国调 / 混改、新华资产</td></tr>
      <tr><td>累计 IOI 目标（HKD M）</td><td>≥ 230（Tier-1 合计置信中位数）</td></tr>
      <tr><td>合规口径</td><td>HKEx 静默期 · 仅可引用招股书 / 已批准 IM</td></tr>
      <tr><td>团队配置</td><td>Lead Banker (MD) · VP · Analyst（共 3 人，全员 in-person）</td></tr>
      <tr><td>关键交通段</td><td>14:35 CBD → 中关村（晚高峰 40-50 min 高风险）</td></tr>
    </tbody>
  </table>

  <h2>当日成功标准 · Day-1 Success Criteria</h2>
  <ul>
    <li><strong>Tier-1 收敛</strong>：诚通 + 新华资产 各给出 IOI 区间、锁定期上限、决策时间表</li>
    <li><strong>Tier-2 关系</strong>：中国移动、小米 提供后续业务协同 / 战投部对接通道</li>
    <li><strong>Tier-3 情报</strong>：智谱 AI 给出 AI 赛道 IPO 估值锚共识 + 投融资环境读数</li>
    <li><strong>当晚 21:00 前</strong>：Daily Summary 发到 syndicate desk + deal captain</li>
  </ul>

  <div class="notice">
    <strong>合规前置确认（强制）</strong>：本次为港股 IPO 招股阶段路演，全场对外口径仅限招股书及法务签批的
    IM/Talking Points。<strong>禁止</strong> 披露任何 outside-prospectus 数据、价格指引或其他 cornerstone
    投资人名单。Reg FD / SFC fair-disclosure 在场监管。
  </div>
</section>

<!-- ====== 2. 逐时行程 ====== -->
<section class="section">
  <h1>2 · 逐时行程 · Hour-by-Hour Schedule</h1>

  <div class="timeline">
    <div class="item"><span class="time">07:30</span><span class="label">团队 standup（30 分钟）</span><div class="sub">地点：酒店 / 办公室 · 校准当日 talking points 与法务红线</div></div>
    <div class="item"><span class="time">08:00</span><span class="label">出发 → 金融街</span><div class="sub">Analyst 提前 90 分钟叫车，预留早高峰</div></div>
    <div class="item"><span class="time">09:00</span><span class="label">抵达中国移动总部，楼宇登记</span><div class="sub">金融街 29 号 · 央企登记 buffer 30 min</div></div>

    <div class="item meeting"><span class="time">09:30–10:30</span><span class="label">Meeting 1 · 中国移动</span><div class="sub">T2 战略 / 潜在锚定 · 主题：5G+AI 协同 / 行业大模型</div></div>

    <div class="item"><span class="time">10:30–10:35</span><span class="label">即时反馈录入</span><div class="sub">Analyst on-site 录 feedback tracker</div></div>
    <div class="item"><span class="time">10:35–10:50</span><span class="label">步行 → 国新控股</span><div class="sub">金融街 29 号 → 金融街 25 号 · 约 0.5 km · 不打车</div></div>

    <div class="item meeting"><span class="time">11:00–12:00</span><span class="label">Meeting 2 · 中国诚通 / 国调 / 混改</span><div class="sub"><strong>T1 核心 LP · 当日最重要场次</strong></div></div>

    <div class="item"><span class="time">12:05</span><span class="label">出租车 → CBD（约 28-38 分钟）</span><div class="sub">起：金融街 25 号 ・ 终：建国门外大街丙 12 号</div></div>
    <div class="item"><span class="time">12:45–13:25</span><span class="label">工作午餐（楼内简餐 / SKP-S）</span><div class="sub">上午两场复盘 · 调整下午口径</div></div>

    <div class="item meeting"><span class="time">13:30–14:30</span><span class="label">Meeting 3 · 新华资产</span><div class="sub"><strong>T1 险资 cornerstone · 偿付能力关键</strong></div></div>

    <div class="item"><span class="time">14:35</span><span class="label">出租车 → 中关村东路（40-50 分钟）⚠ 高风险</span><div class="sub">建议提前与新华资产协调 13:30-14:15 + 15min buffer</div></div>

    <div class="item meeting"><span class="time">15:00–16:00</span><span class="label">Meeting 4 · 智谱 AI</span><div class="sub">T3 同业 / 行业 benchmark</div></div>

    <div class="item"><span class="time">16:00</span><span class="label">出租车 → 小米科技园（25-35 分钟）</span><div class="sub">京新高速 vs 学清路 / 八达岭高速辅路；如延误协调 17:00 起</div></div>

    <div class="item meeting"><span class="time">17:00–18:00（建议）</span><span class="label">Meeting 5 · 小米</span><div class="sub">T2 战略 + 港股 IPO 先例 · 战投部 + 顺为资本双线</div></div>

    <div class="item"><span class="time">18:00–18:30</span><span class="label">当日 wrap-up + Daily Summary 草稿</span><div class="sub">就近咖啡 / 酒店 · Analyst 主导</div></div>
    <div class="item"><span class="time">21:00 前</strong></span><span class="label">发出 Daily Summary 给 syndicate desk + deal team</span><div class="sub">Lead Banker 签发</div></div>
  </div>

  <div class="notice">
    <strong>建议同步动作</strong>（行程发出前完成）：
    <ul style="margin:1mm 0 0 6mm">
      <li>与<strong>新华资产</strong>协调：会议改 13:30-14:15（提前 15 分钟散场）</li>
      <li>与<strong>小米</strong>协调：改 17:00-18:00（中关村→清河晚高峰更稳）</li>
      <li>与<strong>诚通 IR</strong>：确认地点（默认国新 25 号 11F），提前 1 天确认会议室号 + 接待联系人手机</li>
    </ul>
  </div>
</section>

<!-- ====== 3. Prep Cards ====== -->
<section class="section">
  <h1>3 · 5 场会议简报 · Prep Cards</h1>

  <!-- Card 1 -->
  <div class="card tier-2">
    <div class="card-header">
      <div class="card-title">① 中国移动 · 09:30–10:30 <span class="card-tier">T2</span></div>
      <div class="card-time">09:30–10:30 · 金融街 29 号</div>
    </div>
    <div class="card-block">
      <div class="block-label">对方核心画像</div>
      央企巨头，A+H 双重上市（600941 / 0941.HK），2024 收入 ~¥1.04 万亿 [VERIFY]。<br/>
      战略投资 / 产业基金参与外部 IPO 锚定频率：<strong>低</strong>，需走集团决策流程。<br/>
      本场更适合做战略关系 + 行业协同试探，而非短期 IOI 收集。
    </div>
    <div class="card-block">
      <div class="block-label">关键问题（按优先级）</div>
      <ol>
        <li>移动云 / 政企事业部对你方标的所属赛道的采购 / 合作意愿？</li>
        <li>中国移动（或旗下基金）是否有 IPO 锚定的过往案例 + 决策窗口？</li>
        <li>若以"战略 cornerstone + 业务绑定"形式参与，标准化条款有哪些？</li>
      </ol>
    </div>
    <div class="card-block">
      <div class="block-label">红线 / Red Lines</div>
      <div class="redline">不主动报价 · 不承诺独家 / 排他 · 不披露 outside-prospectus 数据</div>
    </div>
    <div class="card-block">
      <div class="block-label">期望产出</div>
      <div class="target">关系建立 + 业务协同 follow-up 路径（48h 内 capability deck）</div>
    </div>
  </div>

  <!-- Card 2 -->
  <div class="card tier-1">
    <div class="card-header">
      <div class="card-title">② 中国诚通 / 国调 / 混改 · 11:00–12:00 <span class="card-tier">T1</span></div>
      <div class="card-time">11:00–12:00 · 国新控股 金融街 25 号 11F</div>
    </div>
    <div class="card-block">
      <div class="block-label">对方核心画像</div>
      国务院国资委直管央企，旗下 <strong>国调基金二期 + 央企混改基金 + 央企科创基金</strong>，
      AUM ≥ ¥5,000 亿 [VERIFY]。历史参与过中国电信 / 中海油服等央企 IPO cornerstone。<br/>
      决策链：投资团队（国新控股 11F）→ 投决会 → 集团备案。<br/>
      <strong>本场目标</strong>：confirm IOI 区间 + 锁定期可接受度。
    </div>
    <div class="card-block">
      <div class="block-label">关键问题</div>
      <ol>
        <li>国调基金二期对标的所在行业 + 估值区间（PE / PB / EV/EBITDA）是否在投资范围？</li>
        <li>可承诺 IOI 区间 + 锁定期上限？（6 / 12 / 18 个月）</li>
        <li>决策时间表：IPO 定价前需要多少 trading days 完成内部投委 + 国资委备案？</li>
        <li>共投权 / 后续轮跟投权 / Board 观察员席位是否必要条款？</li>
      </ol>
    </div>
    <div class="card-block">
      <div class="block-label">红线</div>
      <div class="redline">不可披露 Tier-1 其他 cornerstone 投资人 · 不可承诺最终 allocation 数量</div>
    </div>
    <div class="card-block">
      <div class="block-label">期望产出</div>
      <div class="target">一个 IOI 区间（HKD M）+ 锁定期上限 + 决策窗口（days to pricing）</div>
    </div>
  </div>

  <!-- Card 3 -->
  <div class="card tier-1">
    <div class="card-header">
      <div class="card-title">③ 新华资产 · 13:30–14:30 <span class="card-tier">T1</span></div>
      <div class="card-time">13:30–14:30 · 朝阳 CBD 新华人寿大厦</div>
    </div>
    <div class="card-block">
      <div class="block-label">对方核心画像</div>
      新华人寿（A+H 上市）旗下资管，2024 AUM ~¥1.5 万亿 [VERIFY]。<br/>
      险资 IPO cornerstone 偏好：长期资金匹配 + 偿付能力（C-ROSS II）下的风险因子优化。<br/>
      历史案例：保险资金参与多个央企港股 IPO cornerstone。<br/>
      <strong>保险账户对回撤敏感，对长期持有 + 稳定股息率有结构性需求。</strong>
    </div>
    <div class="card-block">
      <div class="block-label">关键问题</div>
      <ol>
        <li>当前 IPO 锚定投资总额度的余位？2026 配置增量？</li>
        <li>对标的（行业 + 估值）+ 派息政策预期？</li>
        <li>cornerstone 的 IOI 区间 + 锁定期下偿付能力压力测算？</li>
        <li>是否要求每季度 IR report + 业绩沟通频率？</li>
      </ol>
    </div>
    <div class="card-block">
      <div class="block-label">红线</div>
      <div class="redline">不可暗示估值优惠或 sweetheart deal（监管敏感）· 不可承诺业绩 guidance</div>
    </div>
    <div class="card-block">
      <div class="block-label">期望产出</div>
      <div class="target">IOI 区间 + 偿二代下可承接的最大份额 + IR 报告频率诉求</div>
    </div>
  </div>

  <!-- Card 4 -->
  <div class="card tier-3">
    <div class="card-header">
      <div class="card-title">④ 智谱 AI · 15:00–16:00 <span class="card-tier">T3</span></div>
      <div class="card-time">15:00–16:00 · 海淀中关村东路</div>
    </div>
    <div class="card-block">
      <div class="block-label">对方核心画像</div>
      清华系大模型独角兽，2024-2025 估值 ~¥200 亿 [VERIFY]。<br/>
      自身亦在筹备未来 IPO，与你方可能存在赛道交集（若标的是 AI / 算力 / 应用相关）。<br/>
      <strong>非投资人，定位为行业 benchmark + 行业情报源。</strong>
    </div>
    <div class="card-block">
      <div class="block-label">关键问题</div>
      <ol>
        <li>大模型行业 IPO 估值锚定共识（VC 期估值 → IPO 估值的折溢价）？</li>
        <li>标的与智谱的业务协同 / 客户重叠 / 算力共享可能性？</li>
        <li>是否考虑产业基金 / 战略投资形式参与你方 IPO？（小概率 upside）</li>
      </ol>
    </div>
    <div class="card-block">
      <div class="block-label">红线</div>
      <div class="redline">不交换任何 MNPI · 不暗示对智谱自身 IPO 节奏的判断</div>
    </div>
    <div class="card-block">
      <div class="block-label">期望产出</div>
      <div class="target">行业情报 + 可能的合作 follow-up 通道</div>
    </div>
  </div>

  <!-- Card 5 -->
  <div class="card tier-2">
    <div class="card-header">
      <div class="card-title">⑤ 小米 · 17:00–18:00 <span class="card-tier">T2</span></div>
      <div class="card-time">17:00–18:00 · 海淀清河 小米科技园</div>
    </div>
    <div class="card-block">
      <div class="block-label">对方核心画像</div>
      港股蓝筹（1810.HK），2024 收入 ~¥3,659 亿 [VERIFY]，三大业务：手机 + AIoT + 汽车。<br/>
      战投平台：<strong>小米战投部 + 顺为资本 + 雷军办公室</strong>（不同决策路径）。<br/>
      港股 IPO 经验丰富（2018 年上市），对港股 lock-up + 流动性问题有第一手认知。
    </div>
    <div class="card-block">
      <div class="block-label">关键问题</div>
      <ol>
        <li>小米战投对标的赛道的 cornerstone 偏好？是否要求业务绑定（供应链 / 客户）？</li>
        <li>顺为资本是否可作为 GP 同步参与？</li>
        <li>港股 IPO 静默期 + book-building 实操经验（询问，作为参考）？</li>
        <li>锁定期下流动性安排偏好？</li>
      </ol>
    </div>
    <div class="card-block">
      <div class="block-label">红线</div>
      <div class="redline">港股监管敏感期内不讨论具体定价 · 不交换尚未公开的 deal 细节</div>
    </div>
    <div class="card-block">
      <div class="block-label">期望产出</div>
      <div class="target">战投 / 顺为 / 雷军办公室 对接联系人 + follow-up 路径</div>
    </div>
  </div>
</section>

<!-- ====== 4. 出租车日历 ====== -->
<section class="section">
  <h1>4 · 出租车日历模板 · Taxi Calendar Invites</h1>

  <p>每段做一条日历事件，提前 10 分钟提醒。首选高德企业版 / 滴滴企业版商务；备用 2 个独立账号。</p>

  <table>
    <thead>
      <tr>
        <th style="width:18%">时段</th>
        <th style="width:32%">起 → 终</th>
        <th style="width:12%">距离</th>
        <th style="width:18%">通勤</th>
        <th>风险等级</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>10:30</td><td>移动 → 国新</td><td>0.5 km</td><td>步行 8 min</td><td><span class="tag green">低 / 步行</span></td></tr>
      <tr><td>12:05</td><td>国新 → 新华资产</td><td>6 km</td><td>28–38 min</td><td><span class="tag gold">中</span></td></tr>
      <tr><td>14:35</td><td>新华资产 → 智谱</td><td>18 km</td><td>40–50 min</td><td><span class="tag red">高 ⚠</span></td></tr>
      <tr><td>16:00</td><td>智谱 → 小米</td><td>11 km</td><td>25–35 min</td><td><span class="tag gold">中</span></td></tr>
      <tr><td>18:00+</td><td>小米 → 酒店 / 复盘点</td><td>自选</td><td>—</td><td><span class="tag green">低</span></td></tr>
    </tbody>
  </table>

  <h3>日历模板（复制即可）</h3>
  <div class="code-block">
<span class="gold">[Roadshow Day-1] Leg 3 · 14:35 出租车 新华资产 → 智谱（高风险段）</span>

📍 起点：朝阳 建国门外大街丙 12 号 新华人寿大厦
📍 终点：海淀 知春路 智谱总部

🚖 叫车方式：高德企业版 / 滴滴企业版商务
   备用：单独账号 滴滴 / 美团
   <span class="red">⚠️ 14:30 准时离场，14:35 上车，不晚于 14:40 上路</span>

⏱️ 路途预估：40–50 分钟（晚高峰）
🛡️ 备用电话：[Analyst 手机]
📞 司机绑定后填：______

⚠️ <span class="red">风险</span>：长安街晚高峰；备选路径 北二环→学院南路
   如 14:55 仍未到达 → 提前通知智谱 IR + 协调延 5 min
  </div>
</section>

<!-- ====== 5. HK IPO 合规 ====== -->
<section class="section">
  <h1>5 · 港股 IPO 合规清单 · HK IPO Compliance Checklist</h1>

  <p>本次为港交所 IPO 路演阶段，按 <strong>HKEx Listing Rules + SFC Code of Conduct</strong> 严格执行。
    路演期间任何对外信息披露必须 traceable 到 <strong>已批准招股书（Prospectus）+ 已批准 IM</strong>。</p>

  <h2>5 场会议通用合规守则</h2>
  <ul class="checklist">
    <li>路演时间在港交所聆讯通过后、招股书定稿前的合规窗口 [VERIFY]</li>
    <li>仅引用招股书 + 已批准 IM，不可披露任何 outside-prospectus 数据</li>
    <li>不主动给出价格区间（除非已正式公告）</li>
    <li>不向单一投资人披露其他 cornerstone 名单 / IOI</li>
    <li>不与某一投资人达成"独家" / sweetheart 安排（违反 fair allocation）</li>
    <li>不讨论尚未公开的财务数据（FY-Q4 业绩、未发布的运营 KPI）</li>
    <li>不暗示业绩 guidance / forward-looking statements 越过招股书披露</li>
    <li>所有 IOI 录入需含 investor name / size / price / lock-up / conditions / timestamp / banker owner</li>
    <li>录音 / 录像须征得对方书面同意；默认不录音</li>
    <li>法务 sign-off 的 talking points 已发到团队每一人手机</li>
  </ul>

  <h2>港股特殊事项</h2>
  <div class="notice">
    <strong>Cornerstone Investor Disclosure</strong>：港股 cornerstone 安排会在招股书 PHIP / PSP 阶段公开披露。
    路演中获取 Tier-1 投资人书面承诺后，需 24h 内同步法务，确保 cornerstone 公开披露满足 HKEx 要求。
  </div>
  <div class="notice">
    <strong>Stabilization &amp; Greenshoe</strong>：路演期间不主动讨论 stabilization mechanism / greenshoe option，
    如对方问及 → 引用招股书相关章节，由法务回应。
  </div>
  <div class="danger">
    <strong>SFC fair-disclosure</strong>：港股监管对"公平披露"要求严格。任何 Tier-1 投资人获得的额外信息
    必须在合理时间内同步给 syndicate desk 全部潜在投资人。<strong>禁止</strong>选择性披露。
  </div>

  <h2>对照口径（A股 / 美股 IPO）</h2>
  <table>
    <thead><tr><th>市场</th><th>关键合规口径</th><th>差异点</th></tr></thead>
    <tbody>
      <tr><td>港股 IPO（本次）</td><td>HKEx + SFC · 招股书 / IM</td><td>本方案适用</td></tr>
      <tr><td>A 股 IPO</td><td>证监会 + 沪/深交所</td><td>招股意向书定稿后较宽松；上方守则同样适用</td></tr>
      <tr><td>美股 IPO</td><td>SEC quiet period + Reg FD</td><td>S-1 提交到 IPO 后 25 天禁止 forward-looking 表述</td></tr>
    </tbody>
  </table>
</section>

<!-- ====== 6. Feedback Tracker + Daily Summary ====== -->
<section class="section">
  <h1>6 · 反馈追踪 &amp; 日报模板</h1>

  <h2>Feedback Tracker · 必填 14 字段</h2>
  <table>
    <thead><tr><th style="width:24%">字段</th><th style="width:18%">类型</th><th>示例 / 说明</th></tr></thead>
    <tbody>
      <tr><td>meeting_id</td><td>text</td><td>0527-M2</td></tr>
      <tr><td>investor</td><td>text</td><td>中国诚通 / 国调基金</td></tr>
      <tr><td>date</td><td>date</td><td>2026-05-27</td></tr>
      <tr><td>start / end</td><td>time</td><td>11:00 / 12:00</td></tr>
      <tr><td>attendees_their</td><td>text</td><td>国新控股 王总（投资总监），李经理</td></tr>
      <tr><td>attendees_ours</td><td>text</td><td>MD-张 / VP-李 / Analyst-王</td></tr>
      <tr><td>tier</td><td>T1/T2/T3</td><td>T1</td></tr>
      <tr><td><strong>interest_score</strong></td><td>1-5</td><td>4 = 强烈兴趣，明确进入流程</td></tr>
      <tr><td><strong>IOI_amount_HKD</strong></td><td>numeric</td><td>100,000,000（HKD M）</td></tr>
      <tr><td><strong>price_view</strong></td><td>text</td><td>"招股区间内" / "区间下限附近" / "价高于上限不参与"</td></tr>
      <tr><td><strong>lock_up_acceptable</strong></td><td>text</td><td>"6m OK / 12m 需评估"</td></tr>
      <tr><td>key_concerns</td><td>text</td><td>偿付能力压力 / 行业景气度 / 关键股东锁定</td></tr>
      <tr><td>follow_up_items</td><td>text</td><td>DDQ / 偿付能力测算 / 历史业绩</td></tr>
      <tr><td>owner / timestamp</td><td>text / datetime</td><td>MD-张 / 自动</td></tr>
    </tbody>
  </table>
  <p>节奏：每场结束 5 分钟内即时录入；当日 21:00 前完成 Day-1 全部数据。</p>

  <h2>Daily Summary 模板（21:00 前发 syndicate desk）</h2>
  <div class="code-block">
<span class="gold">[IPO Roadshow Daily Summary] Day 1 · 北京 · 2026-05-27</span>

Deal: [标的代号]
团队: MD-张 / VP-李 / Analyst-王
完成会议: 5 / 5
T1 完成: 2 / 2

<span class="gold">━━━━━━━━━━━━━━━━━━━━━━━━━</span>
<span class="green">🟢 T1 - 诚通 / 国调 / 混改</span>
  • Interest Score: 4 / 5
  • IOI: HKD 150M 范围（区间下限确认，上限待投决）
  • Lock-up: 12 个月 OK
  • Price View: 招股区间中段
  • Follow-up: 投资简报 + 历史 IRR / DPI by vintage（48h 内）
  • 决策窗口: T-7 (定价前 7 个交易日)

<span class="green">🟢 T1 - 新华资产</span>
  • Interest Score: 4 / 5
  • IOI: HKD 80–120M 范围（偿付能力测算待补）
  • Lock-up: 6m 优先，12m 需追加报告
  • Price View: 区间下限附近，对派息敏感
  • Follow-up: 偿付能力适配测算 + 派息政策一页纸

<span class="gold">🟡 T2 - 中国移动</span>
  • Interest Score: 2 / 5 → 战略关系建立
  • IOI: 待集团决策流程
  • Follow-up: 业务协同 follow-up email + capability deck

<span class="gold">🟡 T2 - 小米</span>
  • Interest Score: 3 / 5
  • 战投 + 顺为双线对接，2 周内书面提案
  • Follow-up: 顺为资本 IR 引荐

<span class="gray">🔍 T3 - 智谱</span>
  • Interest Score: 1 / 5 → 关系维护
  • 行业情报: GLM 2026 商业化路径 + 算力供给方案
  • Follow-up: 行业沟通季度化

<span class="gold">━━━━━━━━━━━━━━━━━━━━━━━━━</span>
<span class="red">🔴 重大事项</span>
  1. 诚通投决会下周三，需立即推动 follow-up
  2. 新华资产偿付能力测算关键，48h 内交付
  3. 中国移动战略协同路径需 deal team 内部评估

📅 Day-2 优先动作
  1. 完成新华资产偿付能力测算 + 派息政策一页纸
  2. 诚通 follow-up call confirmed
  3. 启动 Tier-2 北京 LP 拓展（中投、社保、国开金融 等）

📊 累计 IOI（仅 Day 1）
  • T1 IOI 范围: HKD 230–270M
  • T2 IOI 范围: HKD 0–50M（待确认）
  • 合计置信中位数: HKD ~260M

[end of summary]
  </div>
</section>

<!-- ====== 7. Quality Checks ====== -->
<section class="section">
  <h1>7 · 出发前质量校验 · Pre-departure QC</h1>

  <p>5/27 出发前 12 小时务必逐项打勾。任何 ☐ 未变 ✅ → 该项 owner 立即处理。</p>

  <ul class="checklist">
    <li>5 场会议时间 + 楼宇登记 + 接待联系人手机 全部 confirmed</li>
    <li>诚通对接地点已选定（国新 vs 诚通本部）+ 会议室号</li>
    <li>新华资产协调 13:30–14:15 + 小米协调 17:00–18:00 请求已发出</li>
    <li>5 段出租车日历邀请已发；团队成员双账号备份就位</li>
    <li>5 份打印 + 5 份数字版 Prep Card 已分发</li>
    <li>招股书 / IM 由法务最新口径 sign-off [VERIFY]</li>
    <li>静默期合规 talking points 已发到每个团队成员手机</li>
    <li>Feedback tracker 表格创建 + 字段验证完成 + 责任人就位</li>
    <li>法务紧急电话 / 财务 CFO 紧急电话 / 律所电话 卡片打印</li>
    <li>移动 Wi-Fi + 备用充电宝 + 移动会议蓝牙耳机 准备</li>
  </ul>

  <div class="notice">
    <strong>当日紧急联络人卡片（打印分发）</strong>：法务 lead · 律所 partner · CFO · 各 IR 投资人对接人 · 公司接待联系人 ×5
  </div>

  <h2>路演后 D+1 收尾</h2>
  <ol>
    <li>所有 follow-up 资料 24-48h 内交付，由 VP 跟踪进度</li>
    <li>Final Roadshow Summary 在 D+3 完成（含 Tier 分布、地理分布、定价反馈、book-building 建议）</li>
    <li>下一站行程（如 D+2 上海 / 深圳 / 香港）启动 prep</li>
  </ol>

  <p style="margin-top:10mm;color:#6E7681;font-size:8pt;text-align:center">
    — End of Plan · CONFIDENTIAL —
  </p>
</section>

</body>
</html>
"""


def main() -> None:
    font_config = FontConfiguration()
    HTML(string=HTML_BODY).write_pdf(
        target=str(OUT),
        stylesheets=[CSS(string=CSS_STYLE, font_config=font_config)],
        font_config=font_config,
    )
    print(f"✅ PDF generated: {OUT}")
    print(f"   size: {OUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
