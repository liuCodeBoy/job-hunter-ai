"""
push.py - 微信推送（PushPlus）
将分析好的岗位格式化后推送到微信
"""

from __future__ import annotations

import json
import logging
import requests
from datetime import datetime

log = logging.getLogger(__name__)

PUSHPLUS_API = "http://www.pushplus.plus/send"


def format_job_card(job: dict, idx: int) -> str:
    """将岗位信息格式化为 HTML 卡片（PushPlus 支持 HTML）"""
    analysis = {}
    try:
        analysis = json.loads(job.get("analysis", "{}"))
    except Exception:
        pass

    score = job.get("score", 0)
    score_color = "#4CAF50" if score >= 80 else "#FF9800" if score >= 60 else "#9E9E9E"
    score_label = "强烈推荐" if score >= 80 else "值得一看" if score >= 60 else "仅供参考"

    # 关键词标签
    keywords = analysis.get("keywords", [])
    kw_html = "".join(
        f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 8px;'
        f'border-radius:10px;font-size:12px;margin:2px;display:inline-block;">'
        f'{kw}</span>'
        for kw in keywords[:8]
    )

    # 优势 & 差距（有简历时才有）
    match_html = ""
    match = analysis.get("match_analysis", {})
    if match:
        strengths = match.get("strengths", [])
        gaps = match.get("gaps", [])
        if strengths:
            match_html += '<p style="margin:4px 0;color:#2e7d32;font-size:13px;">✅ 优势：' + \
                "、".join(strengths[:3]) + '</p>'
        if gaps:
            match_html += '<p style="margin:4px 0;color:#c62828;font-size:13px;">⚠️ 差距：' + \
                "、".join(gaps[:3]) + '</p>'

    # 面试题（有简历时才有）
    interview_html = ""
    questions = analysis.get("interview_questions", [])
    if questions:
        interview_html = '<p style="margin:8px 0 4px;font-weight:bold;font-size:13px;">🎯 高频面试题</p><ol style="margin:0;padding-left:18px;font-size:12px;color:#555;">'
        for q in questions[:3]:
            interview_html += f'<li style="margin:3px 0">{q["question"]}</li>'
        interview_html += "</ol>"

    # 亮点 & 风险
    highlights = analysis.get("highlights", [])
    red_flags = analysis.get("red_flags", [])
    extra_html = ""
    if highlights:
        extra_html += '<span style="color:#2e7d32;font-size:12px;">💚 ' + " | ".join(highlights) + '</span><br>'
    if red_flags:
        extra_html += '<span style="color:#c62828;font-size:12px;">🔴 ' + " | ".join(red_flags) + '</span>'

    summary = analysis.get("summary", "")

    card = f"""
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin:12px 0;
            background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="font-size:16px;font-weight:bold;color:#212121;">
      {idx}. {job['title']}
    </span>
    <span style="background:{score_color};color:#fff;padding:3px 10px;
                 border-radius:12px;font-size:12px;font-weight:bold;">
      {score}分 · {score_label}
    </span>
  </div>

  <p style="margin:4px 0;color:#555;font-size:14px;">
    🏢 {job['company']} &nbsp;|&nbsp; 💰 {job.get('salary', '薪资面议')}
    &nbsp;|&nbsp; 📍 {job.get('city', '')}
  </p>
  <p style="margin:4px 0;color:#777;font-size:12px;">
    经验：{job.get('experience', '不限')} &nbsp;|&nbsp; 学历：{job.get('degree', '不限')}
  </p>

  {"<p style='margin:6px 0;font-size:13px;color:#333;font-style:italic;'>" + summary + "</p>" if summary else ""}

  <div style="margin:8px 0;">{kw_html}</div>

  {match_html}
  {extra_html}
  {interview_html}

  <p style="margin:10px 0 0;text-align:right;">
    <a href="{job.get('url', '#')}" style="color:#1565c0;font-size:12px;text-decoration:none;">
      👉 查看岗位详情
    </a>
  </p>
</div>
"""
    return card


def build_message(jobs: list, stats: dict) -> tuple[str, str]:
    """构建完整推送消息，返回 (title, content)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"🤖 求职日报 · {len(jobs)} 个新岗位 · {datetime.now().strftime('%m/%d')}"

    header = f"""
<div style="background:linear-gradient(135deg,#1565c0,#42a5f5);color:#fff;
            padding:16px;border-radius:8px;margin-bottom:16px;">
  <h2 style="margin:0 0 4px;font-size:18px;">🤖 AI 求职助手日报</h2>
  <p style="margin:0;font-size:13px;opacity:0.9;">
    {now} &nbsp;|&nbsp; 今日新增 {stats.get('today_new', len(jobs))} 个岗位
    &nbsp;|&nbsp; 累计收录 {stats.get('total', 0)} 个
  </p>
</div>
"""

    job_cards = "".join(format_job_card(job, i + 1) for i, job in enumerate(jobs))

    footer = """
<div style="text-align:center;color:#9e9e9e;font-size:12px;margin-top:16px;
            padding-top:12px;border-top:1px solid #eee;">
  由 job-hunter-ai 驱动 · 基于 OpenClaw · 数据来源 Boss直聘
</div>
"""

    content = header + job_cards + footer
    return title, content


def push_to_wechat(token: str, title: str, content: str) -> bool:
    """通过 PushPlus 推送到微信"""
    if not token:
        log.error("PushPlus token 未配置，跳过推送")
        return False

    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html",
    }

    try:
        resp = requests.post(PUSHPLUS_API, json=payload, timeout=15)
        data = resp.json()
        if data.get("code") == 200:
            log.info(f"微信推送成功: {title}")
            return True
        else:
            log.error(f"推送失败: {data.get('msg', '未知错误')}")
            return False
    except Exception as e:
        log.error(f"推送请求异常: {e}")
        return False


def push_jobs(jobs: list, config: dict, stats: dict) -> bool:
    """主推送入口"""
    if not jobs:
        log.info("没有需要推送的岗位")
        return True

    token = config.get("push", {}).get("pushplus_token", "")
    title, content = build_message(jobs, stats)

    log.info(f"准备推送 {len(jobs)} 个岗位到微信...")
    return push_to_wechat(token, title, content)


def push_summary(message: str, config: dict):
    """推送简单文本摘要"""
    token = config.get("push", {}).get("pushplus_token", "")
    push_to_wechat(token, "🤖 求职助手通知", f"<p>{message}</p>")
