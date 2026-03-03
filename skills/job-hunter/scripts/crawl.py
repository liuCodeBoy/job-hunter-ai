"""
crawl.py - Boss直聘岗位爬虫
通过 OpenClaw Browser 控制用户已登录的 Chrome 发 fetch 请求。

运行方式：
  本模块的 crawl() 需要传入一个 fetch_fn 回调（由 agent 注入）：
    fetch_fn(url: str) -> dict

  如果直接运行（agent 模式），请使用 agent_crawl() 替代，
  它会通过 subprocess 调用 openclaw browser act。
"""

import os
import time
import json
import logging
import subprocess
from urllib.parse import quote

log = logging.getLogger(__name__)

CITY_CODE = {
    "全国": "100010000", "北京": "101010100", "上海": "101020100",
    "广州": "101280100", "深圳": "101280600", "杭州": "101210100",
    "成都": "101270100", "南京": "101190100", "武汉": "101200100",
    "西安": "101110100", "苏州": "101190400", "厦门": "101230200",
    "重庆": "101040100", "天津": "101030100", "长沙": "101250100",
}

EXP_MAP  = {"不限": "", "应届": "102", "1-3年": "103", "3-5年": "104", "5-10年": "105"}
DEG_MAP  = {"不限": "", "大专": "203", "本科": "204", "硕士": "205", "博士": "206"}


def get_salary_code(min_k, max_k):
    if min_k == 0 and max_k == 0: return ""
    if max_k <= 5:  return "402"
    if max_k <= 10: return "403"
    if max_k <= 20: return "404"
    if max_k <= 50: return "405"
    return "406"


def build_search_url(keyword, city, salary_min, salary_max, experience, degree, page=1):
    city_code = CITY_CODE.get(city, "101020100")
    params = [
        "scene=1",
        f"query={quote(keyword)}",
        f"city={city_code}",
        f"page={page}",
        "pageSize=15",
    ]
    sc = get_salary_code(salary_min, salary_max)
    if sc: params.append(f"salary={sc}")
    ec = EXP_MAP.get(experience, "")
    if ec: params.append(f"experience={ec}")
    dc = DEG_MAP.get(degree, "")
    if dc: params.append(f"degree={dc}")
    return "/wapi/zpgeek/search/joblist.json?" + "&".join(params)


def parse_job(raw):
    tags = raw.get("skills", [])
    return {
        "id":          raw.get("encryptJobId", ""),
        "title":       raw.get("jobName", ""),
        "company":     raw.get("brandName", ""),
        "salary":      raw.get("salaryDesc", ""),
        "city":        raw.get("cityName", ""),
        "experience":  raw.get("jobExperience", ""),
        "degree":      raw.get("jobDegree", ""),
        "description": "技术要求：" + "、".join(tags) if tags else "",
        "url":         f"https://www.zhipin.com/job_detail/{raw.get('encryptJobId','')}.html",
        "tags":        tags,
    }


def crawl(config: dict, db_path: str, seen_ids: set, fetch_fn=None) -> list:
    """
    主爬取函数。
    fetch_fn: callable(url) -> dict，由调用方注入（agent 直接传 browser fetch）
    如果为 None，则尝试通过 subprocess 调用 openclaw browser act。
    """
    search      = config["search"]
    crawler_cfg = config.get("crawler", {})
    delay       = crawler_cfg.get("delay", 2)
    max_jobs    = search.get("max_jobs", 15)

    if fetch_fn is None:
        fetch_fn = _make_subprocess_fetch()

    if fetch_fn is None:
        log.error("❌ 无法获取 fetch 函数，请确保 OpenClaw Browser Relay 已连接 Boss直聘标签页")
        return []

    new_jobs = []

    for keyword in search["keywords"]:
        if len(new_jobs) >= max_jobs:
            break

        log.info(f"🔍 搜索: {keyword} | 城市: {search.get('city','上海')}")
        url = build_search_url(
            keyword=keyword,
            city=search.get("city", "上海"),
            salary_min=search.get("salary_min", 0),
            salary_max=search.get("salary_max", 0),
            experience=search.get("experience", "不限"),
            degree=search.get("degree", "不限"),
        )

        time.sleep(delay)
        data = fetch_fn(url)

        if not data or data.get("code") != 0:
            log.warning(f"搜索失败: {data.get('message','') if data else '无响应'}")
            continue

        job_list = data.get("zpData", {}).get("jobList", [])
        log.info(f"  返回 {len(job_list)} 个岗位")

        for raw in job_list:
            if len(new_jobs) >= max_jobs:
                break
            job = parse_job(raw)
            if not job["id"] or job["id"] in seen_ids:
                continue
            log.info(f"  📄 {job['title']} @ {job['company']} ({job['salary']})")
            new_jobs.append(job)
            seen_ids.add(job["id"])

        time.sleep(delay)

    log.info(f"✅ 抓取完成，新增 {len(new_jobs)} 个岗位")
    return new_jobs


def _make_subprocess_fetch():
    """
    通过 openclaw browser act 发 fetch（subprocess 方式，用于独立运行）
    需要 OpenClaw relay 已连接 Boss直聘 tab。
    """
    # 找 target_id
    try:
        import requests as _req
        r = _req.get("http://127.0.0.1:18792/json", timeout=3)
        tabs = r.json() if isinstance(r.json(), list) else []
        target_id = next(
            (t["id"] for t in tabs if "zhipin.com" in t.get("url", "")),
            tabs[0]["id"] if tabs else None
        )
    except Exception:
        target_id = None

    if not target_id:
        return None

    def fetch_fn(url):
        js = f"fetch('{url}',{{credentials:'include'}}).then(r=>r.json()).then(d=>JSON.stringify(d))"
        result = subprocess.run(
            ["openclaw", "browser", "act", "--profile", "chrome",
             "--target", target_id, "--eval", js],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return {}
        try:
            raw = result.stdout.strip()
            if raw.startswith('"'): raw = json.loads(raw)
            return json.loads(raw)
        except Exception:
            return {}

    return fetch_fn
