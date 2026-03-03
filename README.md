# 🤖 job-hunter-ai

> **AI 驱动的智能求职助手** — 自动抓取 Boss直聘岗位、AI 深度分析 JD、简历匹配评分、每日推送到微信

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OpenClaw](https://img.shields.io/badge/Powered%20by-OpenClaw-orange.svg)](https://github.com/openclaw/openclaw)

---

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🕷️ **智能爬虫** | 基于 undetected-chromedriver，绕过 Boss直聘反爬，支持多关键词/城市/薪资筛选 |
| 🧠 **AI 分析** | LLM 深度解析 JD，提取核心技术栈、硬性要求、加分项、潜在风险 |
| 📊 **简历匹配** | 与你的简历对比，输出匹配度评分（0-100）和差距分析 |
| 🎯 **面试准备** | 针对每个岗位自动生成高频面试题 + 答题思路 |
| 📱 **微信推送** | 每天定时推送精美 HTML 卡片到微信，按匹配度排序 |
| 🗄️ **历史去重** | SQLite 本地存储，不重复推送同一岗位 |
| ⏰ **定时运行** | 每天早上 9 点自动触发，零人工干预 |

---

## 📱 效果预览

> 微信收到的推送样式（示意）

```
🤖 AI 求职助手日报
2026-03-03 09:00 | 今日新增 15 个岗位 | 累计收录 87 个

┌─────────────────────────────────────┐
│ 1. Python 后端工程师          85分 强烈推荐 │
│ 🏢 某互联网公司 | 💰 25-40K | 📍 上海    │
│ "经验和技术栈高度匹配，建议优先投递"       │
│                                     │
│ 技术标签: Python Redis MySQL Docker  │
│ ✅ 优势: Python经验符合、有大厂经历     │
│ ⚠️ 差距: 缺少K8s经验                  │
│                                     │
│ 🎯 高频面试题:                        │
│  1. 介绍一下你对Redis的理解             │
│  2. 如何优化慢查询SQL                  │
│                                     │
│              👉 查看岗位详情           │
└─────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt

# 需要安装 Chrome 浏览器（用于爬虫）
# Ubuntu/Debian:
sudo apt install google-chrome-stable
# macOS:
brew install --cask google-chrome
```

### 2. 获取 PushPlus Token

1. 访问 [pushplus.plus](https://www.pushplus.plus)
2. 微信扫码登录
3. 复制首页的 Token

### 3. 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入你的搜索关键词、城市、薪资范围和 PushPlus Token：

```yaml
search:
  keywords:
    - "Python后端"
    - "Java开发"
  city: "上海"
  salary_min: 15
  salary_max: 50

push:
  pushplus_token: "你的token"
  push_hour: 9
  min_score: 60   # 只推送匹配分 ≥ 60 的岗位
```

### 4. 填写简历（可选，但强烈推荐）

编辑 `resume.md`，填入你的简历内容，格式随意：

```markdown
## 技术栈
Python / Django / Redis / MySQL / Docker

## 工作经历
某公司 后端开发工程师 2022-至今
- 负责用户系统开发，日活 100 万+
- ...
```

> 填写简历后，AI 会输出针对每个岗位的匹配度评分和面试题。

### 5. 运行

```bash
# 手动运行一次
python skills/job-hunter/scripts/main.py

# 跳过爬虫，只分析推送已有数据
python skills/job-hunter/scripts/main.py --skip-crawl

# 只爬取分析，不推送
python skills/job-hunter/scripts/main.py --skip-push
```

### 6. 设置定时任务（Linux/macOS）

```bash
# 每天早上 9:00 自动运行
crontab -e

# 添加：
0 9 * * * cd /path/to/job-hunter-ai && python skills/job-hunter/scripts/main.py >> data/cron.log 2>&1
```

---

## 📁 项目结构

```
job-hunter-ai/
├── README.md
├── config.example.yaml     # 配置模板
├── config.yaml             # 你的配置（不提交 Git）
├── resume.md               # 你的简历（不提交 Git）
├── requirements.txt
├── data/                   # 运行时数据（自动创建）
│   ├── jobs.db             # SQLite 数据库
│   └── job-hunter.log      # 运行日志
└── skills/
    └── job-hunter/
        ├── SKILL.md
        └── scripts/
            ├── main.py         # 主入口
            ├── crawl.py        # Boss直聘爬虫
            ├── analyze.py      # AI 分析
            ├── push.py         # 微信推送
            └── db.py           # 数据库操作
```

---

## ⚙️ 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `search.keywords` | 搜索关键词列表 | - |
| `search.city` | 城市 | 上海 |
| `search.salary_min/max` | 薪资范围（K） | 不限 |
| `search.experience` | 经验要求 | 不限 |
| `search.max_jobs` | 每次最多抓取数量 | 20 |
| `push.pushplus_token` | PushPlus Token | - |
| `push.min_score` | 最低推送分数 | 0 |
| `push.max_push` | 每次最多推送数量 | 10 |
| `crawler.headless` | 无头模式 | true |
| `crawler.delay` | 请求间隔（秒） | 2 |

---

## 🤝 基于 OpenClaw

本项目基于 [OpenClaw](https://github.com/openclaw/openclaw) AI Agent 框架构建。

OpenClaw 是一个开源的私人 AI 助手框架，支持 WhatsApp、Telegram、Discord 等多平台，具备工具调用、长期记忆、多 Agent 协作等能力。

如果你想把求职助手接入 Telegram/WhatsApp，可以将本项目作为 OpenClaw Skill 使用：

```bash
# 复制到 OpenClaw workspace
cp -r skills/job-hunter ~/.openclaw/workspace/skills/

# 在对话中触发
> 帮我运行求职助手
```

---

## ❓ 常见问题

**Q: 运行报错 `Login required`？**  
A: 第一次运行时，Boss直聘可能要求登录。设置 `crawler.headless: false`，会弹出浏览器窗口，手动扫码登录后程序自动继续。登录 Cookie 会保存，后续无需重复登录。

**Q: 抓取到的岗位很少？**  
A: Boss直聘有反爬限制，增大 `crawler.delay`（建议 3-5 秒），或减少 `search.max_jobs`。

**Q: 微信没收到推送？**  
A: 检查 PushPlus Token 是否正确，以及微信是否关注了"推送加"公众号。

**Q: AI 分析质量不好？**  
A: 确保配置了有效的 LLM API（OpenClaw 默认使用 Claude），并且 JD 描述足够完整。

---

## 📄 License

MIT License — 自由使用，欢迎 PR 和 Star ⭐

---

<p align="center">
  Made with ❤️ · 如果对你有帮助，欢迎 Star ⭐
</p>
