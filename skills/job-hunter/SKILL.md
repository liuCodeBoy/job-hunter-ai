---
name: job-hunter
description: AI求职助手，自动抓取Boss直聘岗位、AI分析JD匹配度、每日推送到微信
---

# job-hunter Skill

每天自动执行：抓取 Boss直聘 → AI 分析 → 推送微信

## 运行

```bash
cd /path/to/job-hunter-ai
python skills/job-hunter/scripts/main.py --config config.yaml
```

## 参数

- `--config`：配置文件路径（默认 config.yaml）
- `--skip-crawl`：跳过爬虫，只分析推送
- `--skip-push`：只爬取分析，不推送
