"""
analyze.py - JD 分析 + 简历匹配
调用 LLM 对岗位进行深度分析

LLM 配置优先级（从高到低）：
  1. 环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
  2. config.yaml 中的 llm 配置项
  3. ~/.openclaw/openclaw.json（OpenClaw 用户专用）
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


def _load_llm_config(app_config: dict = None) -> dict:
    """
    加载 LLM 配置，优先级：
    1. 环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
    2. config.yaml 中的 llm 配置项（通过 app_config 传入）
    3. ~/.openclaw/openclaw.json（OpenClaw 用户专用）
    """
    # 1. 环境变量
    env_key = os.environ.get("LLM_API_KEY", "")
    if env_key:
        return {
            "api_key":  env_key,
            "base_url": os.environ.get("LLM_BASE_URL", "https://api.anthropic.com"),
            "model":    os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022"),
        }

    # 2. config.yaml 中的 llm 配置
    if app_config:
        llm_cfg = app_config.get("llm", {})
        if llm_cfg.get("api_key"):
            return {
                "api_key":  llm_cfg["api_key"],
                "base_url": llm_cfg.get("base_url", "https://api.anthropic.com"),
                "model":    llm_cfg.get("model", "claude-3-5-sonnet-20241022"),
            }

    # 3. ~/.openclaw/openclaw.json（兜底）
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path, encoding="utf-8") as f:
            d = json.load(f)
        pp = d.get("models", {}).get("providers", {}).get("ppinfra", {})
        model_full = (
            d.get("agents", {})
             .get("defaults", {})
             .get("model", {})
             .get("primary", "")
        )
        parts = model_full.split("/")
        model_name = "/".join(parts[1:]) if len(parts) > 1 else model_full
        if pp.get("apiKey"):
            return {
                "api_key":  pp["apiKey"],
                "base_url": pp.get("baseUrl", ""),
                "model":    model_name or "claude-sonnet-4-6",
            }
    except Exception:
        pass

    return {}


def call_llm(prompt: str, app_config: dict = None) -> str:
    """调用 LLM，返回文本"""
    cfg = _load_llm_config(app_config)
    if not cfg.get("api_key"):
        log.error(
            "未找到 LLM API Key，请通过以下任一方式配置：\n"
            "  1. 环境变量：export LLM_API_KEY=sk-xxx\n"
            "  2. config.yaml 中添加 llm.api_key\n"
            "  3. 安装 OpenClaw 并配置 ppinfra provider"
        )
        return ""

    try:
        import anthropic
        client = anthropic.Anthropic(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"] or None,
        )
        message = client.messages.create(
            model=cfg["model"],
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        log.error(f"LLM 调用失败: {e}")
        return ""


def extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log.warning(f"无法解析 LLM 输出为 JSON: {text[:200]}")
    return {}


def analyze_job(job: dict, resume: str = "", app_config: dict = None) -> dict:
    """分析单个岗位，返回 {score, analysis}"""
    description = job.get("description", "")
    if not description:
        log.warning(f"岗位无 JD 描述，跳过分析: {job.get('title', '')}")
        return {"score": 50, "analysis": "{}"}

    if resume:
        prompt = ANALYZE_PROMPT_WITH_RESUME.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            salary=job.get("salary", ""),
            experience=job.get("experience", ""),
            degree=job.get("degree", ""),
            description=description[:3000],
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
    raw = call_llm(prompt, app_config)
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


def batch_analyze(jobs: list, resume_path: str = "", app_config: dict = None) -> list:
    """批量分析岗位列表"""
    resume = load_resume(resume_path)
    if resume:
        log.info("已加载简历，将进行匹配评分")
    else:
        log.info("未找到简历，仅做岗位质量评分")

    results = []
    for job in jobs:
        try:
            result = analyze_job(job, resume, app_config)
            job["score"] = result["score"]
            job["analysis"] = result["analysis"]
        except Exception as e:
            log.error(f"分析失败 {job.get('title', '')}: {e}")
            job["score"] = 50
            job["analysis"] = "{}"
        results.append(job)

    return results
