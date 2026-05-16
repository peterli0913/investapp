# 炒股助手 · 信息收集与辅助决策（Stock Assistant）

一款面向专业散户的多模块炒股辅助 app，基于 **Streamlit**。

- **5 个核心模块**：火热板块动态、TACO 动态、热门股票追踪、港股打新、新股推荐
- **每日北京时间 06:30 自动刷新**，也支持手动一键刷新
- **自带回测训练**：用 1 年前的行情做预测，用 11 个月前的真实走势作为标签，验证策略
- **专业金融审美**：深色主题 + 金色高亮 + 红涨绿跌
- 两种发布形态：**Streamlit Cloud** 部署 / **PyInstaller** 打包成可执行文件

---

## 1. 本地运行

```bash
# Python 3.10+ 推荐
pip install -r requirements.txt

# （可选）复制配置：填写 LLM API Key 才能启用 AI 分析；不填会走启发式回退
cp .env.example .env

streamlit run streamlit_app.py
```

启动后访问 <http://localhost:8501>。

### 关于 LLM Key

支持任何兼容 OpenAI API 协议的服务。**默认使用 DeepSeek**：

| 服务 | OPENAI_BASE_URL | 推荐模型 | 备注 |
|---|---|---|---|
| **DeepSeek** ⭐ | `https://api.deepseek.com` | `deepseek-v4-flash` / `deepseek-v4-pro` | 国内速度快、价格低 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | 全球通用 |
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | 国内可用 |

#### DeepSeek 模型选择（2026 起 V3 系列已合并到 V4）

| 模型 | 适用 | 价格（1M tokens, 输入/输出） |
|---|---|---|
| `deepseek-v4-flash` | 日常刷新、新闻总结、情绪打分 | $0.14 / $0.28 |
| `deepseek-v4-pro` | 重要决策、深度推理（思考模式） | $0.435 / $0.87（当前 75% 折扣） |

> 旧名 `deepseek-chat` 和 `deepseek-reasoner` 仍然兼容（实际指向 v4-flash 的非思考 / 思考模式），但将被官方弃用。建议直接用新名字。

#### 自动模型分级（推荐方案）

app 会**按调用场景自动切换模型**，无需手动选：

| 场景 | 默认 tier | 默认模型 |
|---|---|---|
| 板块新闻总结、情绪打分 | `fast` | `deepseek-v4-flash` |
| TACO 全球影响分析 | `deep` | `deepseek-v4-pro` |
| 追踪股操作建议（买卖判断） | `deep` | `deepseek-v4-pro` |
| 港股打新申购建议 | `deep` | `deepseek-v4-pro` |
| 新股推荐评级 | `deep` | `deepseek-v4-pro` |

在 `.env` 中独立配置：

```bash
OPENAI_MODEL_FAST=deepseek-v4-flash
OPENAI_MODEL_DEEP=deepseek-v4-pro
```

想全用便宜模型省钱 → 两个都设 `deepseek-v4-flash`；想全用深度模型 → 两个都设 `deepseek-v4-pro`。

#### 排查 `Authentication Fails (governor)` 错误

这是 DeepSeek 的特定错误，含义是**请求里没带 `Authorization` header**（不是 key 错）。最常见的原因：

1. `.env` 中 `OPENAI_API_KEY` 是空字符串或多了空格 / 引号
2. 没有重启 streamlit（应用启动时只读一次 `.env`）
3. base URL 写成了不存在的形式

**最快定位方式**：进入应用的 *设置 / 自选股* 页面，点 **🔌 测试 LLM 连接**，会真实发一次请求并把 base_url / 模型 / 原始错误响应完整打出来。

没有 key 也可以跑，所有 AI 模块会回退到启发式实现（仅做信息聚合，不做主观判断）。

---

## 2. 部署到 Streamlit Cloud

1. 把仓库 push 到 GitHub。
2. 登录 <https://share.streamlit.io>，新建 app，**Main file path** 必须填 `streamlit_app.py`。
3. 在 **App Settings → Secrets** 里粘贴下面这段（注意：Streamlit Cloud Secrets 是 **TOML 格式**，字符串必须用**双引号**包裹，不能用 `KEY=VALUE` 的 .env 写法）：

    ```toml
    OPENAI_API_KEY = "sk-你的DeepSeekKey"
    OPENAI_BASE_URL = "https://api.deepseek.com"
    OPENAI_MODEL_FAST = "deepseek-v4-flash"
    OPENAI_MODEL_DEEP = "deepseek-v4-pro"
    DAILY_UPDATE_HHMM = "06:30"
    TIMEZONE = "Asia/Shanghai"
    ```

4. 点 **Save**，应用自动重启。Streamlit Cloud 在长时间无访问时会休眠，可用 [UptimeRobot](https://uptimerobot.com) 每 10 分钟 ping 一次保持调度器存活。

### Streamlit Cloud 部署排错

| 现象 | 真实原因 | 修复 |
|---|---|---|
| 部署后页面打开是空白 / 一直转圈 | 应用启动报错。打开 **Manage app → Logs** 看 Python traceback | 把 traceback 完整发我 |
| 设置页 ping 测试报 `OPENAI_API_KEY 未配置` | Secrets 格式不对（**最常见**：用了 `KEY=VALUE` 而不是 `KEY = "VALUE"`） | Secrets 必须是 TOML 格式，字符串两边加双引号 |
| `Authentication Fails (governor)` | Authorization header 没被带上 | 同上：检查 Secrets 引号；改完点 Save 等自动重启 |
| `ModuleNotFoundError: akshare / yfinance` | requirements.txt 没被识别 | 确认 `requirements.txt` 在仓库根目录（不要放在子目录） |
| `unhashable type: 'list'` 之类奇怪错误 | Python 版本不对 | App Settings → Python version 选 **3.11** 或 **3.12** |

修改 Secrets 后**不需要 Reboot**，Streamlit Cloud 会自动 reload。如果界面没自动刷新，强制刷新浏览器即可。

---

## 3. 打包为 exe / 单文件可执行

```bash
pip install pyinstaller
python scripts/build_exe.py
```

完成后产物在 `dist/StockAssistant/`，双击 `StockAssistant.exe`（Windows）或对应可执行文件即可，启动后浏览器自动打开。

> macOS / Linux 也可直接跑 `python scripts/build_exe.py`，产出对应平台的可执行文件夹。

---

## 4. 项目结构

```
.
├── streamlit_app.py            # 应用入口（Streamlit Cloud 主文件）
├── app/
│   ├── pages/                  # 5 个业务页面 + 首页 + 回测 + 设置
│   ├── modules/                # 5 个模块的业务编排
│   │   ├── sectors.py          # 火热板块动态
│   │   ├── taco.py             # Trump 新闻与影响分析
│   │   ├── tracked_stocks.py   # 自选股追踪
│   │   ├── ipo.py              # 港股打新
│   │   └── recommendations.py  # 新股推荐
│   ├── services/               # 底层数据 / AI 服务
│   │   ├── market_data.py      # akshare + yfinance 封装
│   │   ├── news_feed.py        # RSS / Google News 聚合
│   │   └── llm_client.py       # LLM 客户端（OpenAI 协议）
│   ├── scheduler/jobs.py       # APScheduler 定时刷新
│   ├── backtest/engine.py      # 回测引擎
│   ├── storage/db.py           # SQLite 持久化
│   ├── utils/                  # 配置、时区、日志
│   └── assets/theme.css        # 金融风深色主题
├── scripts/
│   ├── build_exe.py            # PyInstaller 打包
│   └── launcher.py             # exe 内启动 Streamlit + 浏览器
├── .streamlit/config.toml      # 主题配置
├── .env.example                # 配置模板
└── requirements.txt
```

---

## 5. 数据源说明

| 数据 | 来源 | 备注 |
|---|---|---|
| A 股 / 港股 K 线、板块涨跌幅 | [akshare](https://akshare.akfamily.xyz/) | 开源免费 |
| 美股 K 线 | [yfinance](https://github.com/ranaroussi/yfinance) | 开源免费 |
| 新闻聚合 | Google News RSS / 新浪财经 / 华尔街见闻 等 | 公开 RSS |
| 港股新股日历 | akshare → 东方财富 | akshare 不同版本接口名不同，已做容错 |
| Trump 新闻 | Google News + Reuters/CNBC/MarketWatch RSS | 公开 RSS |

如果某个源短时返回空（限流、网络），模块会保留上一次的快照，不会丢数据。

---

## 6. 回测训练

`回测训练` 页面实现你描述的训练 / 验证流程：

> 用 1 年前的股市信息进行预测，然后看 11 个月前的真实走向。

内置 3 种简单可解释的策略（均值回归 / 动量 / 均线交叉），先用 2 年滚动样本统计胜率、平均收益、累计收益，再用"1 年前 → 11 个月前"做一次样本外诊断。

后续可以接入 LLM 在 `app/backtest/engine.py` 中替换 `_signal_*` 函数，对**行情 + 新闻**做联合预测，再由 `module_history` 记录每次预测的事后表现，长期累积成回测数据库。

---

## 7. 风险提示

本应用聚合的所有信息、分析与建议**仅供学习交流**，不构成投资建议。请独立做出投资决策。
