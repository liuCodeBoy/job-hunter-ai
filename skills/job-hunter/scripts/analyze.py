"""
analyze.py - JD 分析 + 简历匹配
调用 OpenClaw Agent（LLM）对岗位进行深度分析
"""

import json
import re
import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)


ANALYZE_PROMPT_NO_RESUME = """你是一个资深 HR 顾问，请对以下岗位 JD 进行深度分析。

## 岗位信息
- 职位：{title}
- 公司：{company}
- 薪资：{salary}
- 经验要求：{experience}
- 学历要求：{degree}

## JD 原文
{description}

## 请输出以下分析（JSON 格式）：
{{
  "score": 75,                          // 岗位综合质量评分 0-100（考虑薪资、公司、JD清晰度）
  "keywords": ["Python", "Redis", ...], // 核心技术关键词（最多10个）
  "requirements": {{
    "must": ["3年以上Python经验", ...],   // 硬性要求
    "nice": ["有大厂经验优先", ...]        // 加分项
  }},
  "highlights": ["福利好", "技术栈新"],   // 岗位亮点（最多3条）
  "red_flags": ["加班严重", ...],         // 潜在风险（最多3条，没有则空数组）
  "summary": "一句话描述这个岗位"          // 简短总结
}}

只输出 JSON，不要其他内容。"""


ANALYZE_PROMPT_WITH_RESUME = """你是一个资深 HR 顾问，请对以下岗位进行分析，并与候选人简历进行匹配评估。

## 岗位信息
- 职位：{title}
- 公司：{company}
- 薪资：{salary}
- 经验要求：{experience}
- 学历要求：{degree}

## JD 原文
{description}

## 候选人简历
{resume}

## 请输出以下分析（JSON 格式）：
{{
  "score": 85,                           // 候选人与岗位匹配度 0-100
  "keywords": ["Python", "Redis", ...],  // 核心技术关键词（最多10个）
  "requirements": {{
    "must": ["3年以上Python经验", ...],    // 硬性要求
    "nice": ["有大厂经验优先", ...]         // 加分项
  }},
  "match_analysis": {{
    "strengths": ["Python经验符合", ...], // 候选人优势（最多5条）
    "gaps": ["缺少Kubernetes经验", ...]   // 差距/不足（最多5条）
  }},
  "interview_questions": [               // 针对此岗位的高频面试题（5条）
    {{
      "question": "请介绍一下你对Redis的理解",
      "hint": "重点考察缓存穿透、雪崩、击穿"
    }}
  ],
  "highlights": ["福利好", "技术栈新"],    // 岗位亮点（最多3条）
  "red_flags": ["加班严重", ...],          // 潜在风险（最多3条，没有则空数组）
  "summary": "一句话描述匹配情况"           // 简短总结
}}

只输出 JSON，不要其他内容。"""


def call_llm(prompt: str) -> str:
    """
    调用 LLM。
    在 OpenClaw Skill 环境中，直接用 Python subprocess 调用 openclaw ask 命令；
    也可以通过 OpenAI/Anthropic SDK 直接调用（如果配置了 API key）。
    """
    import subprocess

    result = subprocess.run(
        ["openclaw", "ask", "--no-stream", prompt],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        log.error(f"LLM 调用失败: {result.stderr}")
        return ""
    return result.stdout.strip()


def extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 提取 ```json ... ``` 代码块
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 提取第一个 { ... }
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log.warning(f"无法解析 LLM 输出为 JSON: {text[:200]}")
    return {}


def analyze_job(job: dict, resume: str = "") -> dict:
    """
    分析单个岗位
    返回分析结果 dict，包含 score 和 analysis JSON
    """
    description = job.get("description", "")
    if not description:
        log.warning(f"岗位无 JD 描述，跳过分析: {job['title']}")
        return {"score": 50, "analysis": "{}"}

    if resume:
        prompt = ANALYZE_PROMPT_WITH_RESUME.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            salary=job.get("salary", ""),
            experience=job.get("experience", ""),
            degree=job.get("degree", ""),
            description=description[:3000],  # 限制长度
            resume=resume[:2000],
        )
    else:
        prompt = ANALYZE_PROMPT_NO_RESUME.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            salary=job.get("salary", ""),
            experience=job.get("experience", ""),
            degree=job.get("degree", ""),
            description=description[:3000],
        )

    log.info(f"分析岗位: {job['title']} @ {job['company']}")
    raw = call_llm(prompt)
    result = extract_json(raw)

    score = result.get("score", 50)
    return {
        "score": max(0, min(100, int(score))),
        "analysis": json.dumps(result, ensure_ascii=False),
    }


def load_resume(resume_path: str) -> str:
    """加载简历文件"""
    if not resume_path:
        return ""
    path = Path(resume_path)
    if not path.exists():
        log.info(f"简历文件不存在: {resume_path}，跳过匹配评分")
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def batch_analyze(jobs: list, resume_path: str = "") -> list:
    """批量分析岗位列表"""
    resume = load_resume(resume_path)
    if resume:
        log.info(f"已加载简历，将进行匹配评分")
    else:
        log.info("未找到简历，仅做岗位质量评分")

    results = []
    for job in jobs:
        try:
            result = analyze_job(job, resume)
            job["score"] = result["score"]
            job["analysis"] = result["analysis"]
        except Exception as e:
            log.error(f"分析失败 {job.get('title', '')}: {e}")
            job["score"] = 50
            job["analysis"] = "{}"
        results.append(job)

    return results
