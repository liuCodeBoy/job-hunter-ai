# 🤖 job-hunter-ai

> **AI 驱动的智能求职助手** — 自动抓取 Boss直聘岗位、AI 深度分析 JD、简历匹配评分、每日推送到微信

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🕷️ **智能爬虫** | 通过 OpenClaw Browser Relay 借用已登录的 Chrome，完全绕过 Boss直聘反爬 |
| 🧠 **AI 分析** | LLM 深度解析 JD，提取核心技术栈、硬性要求、加分项、潜在风险 |
| 📊 **简历匹配** | 与你的简历对比，输出匹配度评分（0-100）和差距分析 |
| 🎯 **面试准备** | 针对每个岗位自动生成高频面试题 + 答题思路 |
| 📱 **微信推送** | 每天定时推送精美 HTML 卡片到微信，按匹配度排序 |
| 🗄️ **历史去重** | SQLite 本地存储，不重复推送同一岗位 |

---

## 🚀 快速开始

### 1. 克隆项目 & 安装依赖

```bash
git clone https://github.com/liuCodeBoy/job-hunter-ai.git
cd job-hunter-ai
pip install -r requirements.txt
```

### 2. 配置 LLM API Key

项目使用 Anthropic Claude 做 AI 分析，支持三种配置方式（优先级从高到低）：

**方式一：环境变量（推荐）**
```bash
export LLM_API_KEY="sk-ant-xxxxxx"           # Anthropic 官方 Key
export LLM_BASE_URL="https://api.anthropic.com"  # 可选，默认官方地址
export LLM_MODEL="claude-3-5-sonnet-20241022"    # 可选，默认此模型
```

**方式二：config.yaml**
```yaml
llm:
  api_key: "sk-ant-xxxxxx"
  base_url: "https://api.anthropic.com"  # 使用中转服务可改此地址
  model: "claude-3-5-sonnet-20241022"
```

**方式三：OpenClaw 用户（自动读取）**  
已安装并配置 [OpenClaw](https://github.com/openclaw/openclaw) 的用户无需额外配置，自动读取 `~/.openclaw/openclaw.json`。

> 💡 没有 Anthropic 官方账号？可使用 [ppinfra](https://ppinfra.com) 等中转服务，将 `base_url` 设为 `https://api.ppinfra.com/anthropic`，支持国内访问。

### 3. 配置搜索条件 & 微信推送

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`：

```yaml
search:
  keywords:
    - "Python后端"
    - "大模型应用开发"
  city: "上海"
  salary_min: 25   # 最低薪资（K）
  salary_max: 50

push:
  pushplus_token: "你的token"   # 前往 pushplus.plus 获取
  min_score: 60                 # 只推送匹配分 ≥ 60 的岗位
```

### 4. 填写简历（可选，强烈推荐）

创建 `resume.md`，填入你的简历，格式随意：

```markdown
## 技术栈
Python / FastAPI / LangChain / Redis / MySQL / Docker

## 工作经历
某公司 后端开发工程师 2022-至今
- 负责 RAG 知识库系统开发
- ...
```

> 填写简历后，AI 会输出**针对每个岗位的匹配度评分和高频面试题**。

### 5. 配置 Boss直聘 登录态

本项目通过 **OpenClaw Browser Relay** 借用你已登录的 Chrome 浏览器来抓取数据，完全绕过反爬检测。

**前提：** 安装 [OpenClaw](https://github.com/openclaw/openclaw) 并在 Chrome 中安装 Browser Relay 插件。

```bash
# 安装 OpenClaw
npm install -g openclaw

# 启动 Gateway
openclaw gateway start
```

然后在 Chrome 中：
1. 打开 [Boss直聘](https://www.zhipin.com) 并登录
2. 点击 Chrome 工具栏中的 OpenClaw Browser Relay 图标，开启中继
3. 运行项目即可

### 6. 运行

```bash
# 完整运行（抓取 → 分析 → 推送）
python skills/job-hunter/scripts/main.py --config config.yaml

# 跳过抓取，只分析推送已有数据
python skills/job-hunter/scripts/main.py --config config.yaml --skip-crawl

# 只抓取分析，不推送
python skills/job-hunter/scripts/main.py --config config.yaml --skip-push
```

### 7. 设置定时任务（可选）

```bash
# 每天早上 9:00 自动运行
crontab -e

# 添加：
0 9 * * * cd /path/to/job-hunter-ai && python skills/job-hunter/scripts/main.py --config config.yaml >> data/cron.log 2>&1
```

---

## 📁 项目结构

```
job-hunter-ai/
├── README.md
├── config.example.yaml          # 配置模板（提交到 Git）
├── config.yaml                  # 你的配置（已加入 .gitignore）
├── resume.md                    # 你的简历（已加入 .gitignore）
├── requirements.txt
├── data/                        # 运行时数据，自动创建（已加入 .gitignore）
│   ├── jobs.db                  # SQLite 数据库
│   └── job-hunter.log           # 运行日志
└── skills/
    └── job-hunter/
        └── scripts/
            ├── main.py          # 主入口
            ├── crawl.py         # Boss直聘爬虫（Browser Relay 方案）
            ├── analyze.py       # AI 分析
            ├── push.py          # 微信推送（PushPlus）
            └── db.py            # 数据库操作
```

---

## ⚙️ 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `search.keywords` | 搜索关键词列表 | — |
| `search.city` | 城市 | 上海 |
| `search.salary_min/max` | 薪资范围（K），0 表示不限 | 0 |
| `search.experience` | 经验要求：不限/应届/1-3年/3-5年/5-10年 | 不限 |
| `search.max_jobs` | 每次最多抓取数量 | 15 |
| `search.daily_limit` | 每日累计上限 | 30 |
| `push.pushplus_token` | PushPlus Token | — |
| `push.min_score` | 最低推送分数（0-100） | 0 |
| `push.max_push` | 每次最多推送数量 | 10 |
| `llm.api_key` | LLM API Key | 读环境变量 |
| `llm.base_url` | API 地址 | 官方地址 |
| `llm.model` | 模型名称 | claude-3-5-sonnet-20241022 |

---

## ❓ 常见问题

**Q: 没有安装 OpenClaw 能用吗？**  
A: 爬虫部分依赖 OpenClaw Browser Relay，如果没有安装则无法抓取。但你可以手动准备数据（JSON 格式）直接调用 `analyze.py` 做 AI 分析。

**Q: 支持其他城市吗？**  
A: 支持，修改 `config.yaml` 中的 `search.city` 即可。已内置：北京、上海、广州、深圳、杭州、成都、南京、武汉、西安、苏州等主要城市。

**Q: 微信没收到推送？**  
A: 检查 PushPlus Token 是否正确，以及微信是否关注了「推送加」公众号。

**Q: AI 分析结果质量不好？**  
A: 大部分 Boss直聘 JD 描述本身就很简陋，分析质量取决于 JD 完整度。建议搜索描述更详细的岗位，或填写简历开启匹配模式。

**Q: 支持哪些 LLM 模型？**  
A: 使用 Anthropic SDK，兼容所有 Claude 系列模型。通过修改 `base_url` 也可接入其他兼容接口的服务。

---

## 📄 License

MIT License — 自由使用，欢迎 PR 和 Star ⭐

---

<p align="center">Made with ❤️ · 如果对你有帮助，欢迎 Star ⭐</p>
