"""
crawl.py - Boss直聘岗位爬虫
通过 OpenClaw Browser 控制用户已登录的 Chrome 发 fetch 请求。

核心逻辑：搜索和拉详情必须在同一批次完成，因为 securityId 有时效性。
"""

import time
import json
import logging
from urllib.parse import quote

log = logging.getLogger(__name__)

CITY_CODE = {
    "全国": "100010000", "北京": "101010100", "上海": "101020100",
    "广州": "101280100", "深圳": "101280600", "杭州": "101210100",
    "成都": "101270100", "南京": "101190100", "武汉": "101200100",
    "西安": "101110100", "苏州": "101190400", "厦门": "101230200",
    "重庆": "101040100", "天津": "101030100", "长沙": "101250100",
}

EXP_MAP = {"不限": "", "应届": "102", "1-3年": "103", "3-5年": "104", "5-10年": "105"}
DEG_MAP = {"不限": "", "大专": "203", "本科": "204", "硕士": "205", "博士": "206"}


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


# 一次性搜索 + 拉详情的 JS（securityId 在同一批次内使用，不会过期）
BATCH_FETCH_JS = """
(async () => {{
  // Step1: 搜索
  const searchResp = await fetch('{search_url}', {{credentials:'include'}});
  const searchData = await searchResp.json();
  if (searchData.code !== 0) return JSON.stringify({{error: searchData.message, jobs: []}});

  const jobList = searchData.zpData.jobList || [];

  // Step2: 并发拉详情（限制并发数避免触发频控）
  const results = [];
  for (let i = 0; i < jobList.length; i++) {{
    const j = jobList[i];
    try {{
      const detailResp = await fetch(
        '/wapi/zpgeek/job/detail.json?jobId=' + j.encryptJobId +
        '&lid=' + encodeURIComponent(j.lid) +
        '&securityId=' + encodeURIComponent(j.securityId),
        {{credentials: 'include'}}
      );
      const detail = await detailResp.json();
      const info = (detail.zpData && detail.zpData.jobInfo) || {{}};
      const brand = (detail.zpData && detail.zpData.brandInfo) || {{}};
      results.push({{
        id: j.encryptJobId,
        title: j.jobName,
        company: j.brandName,
        salary: j.salaryDesc,
        city: j.cityName,
        experience: j.jobExperience,
        degree: j.jobDegree,
        url: 'https://www.zhipin.com/job_detail/' + j.encryptJobId + '.html',
        tags: j.skills || [],
        description: info.postDescription || info.desc || '',
        companySize: brand.brandScaleName || '',
        companyStage: brand.brandStageName || '',
        companyIndustry: j.brandIndustry || '',
        welfare: j.welfareList || [],
        areaDistrict: j.areaDistrict || '',
        businessDistrict: j.businessDistrict || '',
      }});
    }} catch(e) {{
      results.push({{
        id: j.encryptJobId,
        title: j.jobName,
        company: j.brandName,
        salary: j.salaryDesc,
        city: j.cityName,
        experience: j.jobExperience,
        degree: j.jobDegree,
        url: 'https://www.zhipin.com/job_detail/' + j.encryptJobId + '.html',
        tags: j.skills || [],
        description: (j.skills||[]).join('、'),
        welfare: j.welfareList || [],
      }});
    }}
    // 每3个请求暂停200ms，避免频控
    if (i % 3 === 2) await new Promise(r => setTimeout(r, 200));
  }}
  return JSON.stringify({{jobs: results, total: searchData.zpData.resCount}});
}})()
"""


def crawl(config: dict, db_path: str, seen_ids: set, fetch_fn=None) -> list:
    """
    主爬取函数。
    fetch_fn: callable(js_code: str) -> str  执行 JS 并返回结果字符串
              由 agent 注入（browser tool evaluate）
    """
    if fetch_fn is None:
        log.error("❌ fetch_fn 未注入，请通过 agent 调用（需要 OpenClaw Browser Relay）")
        return []

    search = config["search"]
    crawler_cfg = config.get("crawler", {})
    delay = crawler_cfg.get("delay", 2)
    max_jobs = search.get("max_jobs", 15)

    new_jobs = []

    for keyword in search["keywords"]:
        if len(new_jobs) >= max_jobs:
            break

        log.info(f"🔍 搜索: {keyword} | 城市: {search.get('city', '上海')}")

        search_url = build_search_url(
            keyword=keyword,
            city=search.get("city", "上海"),
            salary_min=search.get("salary_min", 0),
            salary_max=search.get("salary_max", 0),
            experience=search.get("experience", "不限"),
            degree=search.get("degree", "不限"),
        )

        js = BATCH_FETCH_JS.format(search_url=search_url)

        try:
            result_str = fetch_fn(js)
            data = json.loads(result_str) if isinstance(result_str, str) else result_str
        except Exception as e:
            log.error(f"执行 JS 失败: {e}")
            continue

        if data.get("error"):
            log.warning(f"搜索失败: {data['error']}")
            continue

        jobs = data.get("jobs", [])
        log.info(f"  返回 {len(jobs)} 个岗位，共 {data.get('total', '?')} 个结果")

        for job in jobs:
            if len(new_jobs) >= max_jobs:
                break
            if not job.get("id") or job["id"] in seen_ids:
                continue
            log.info(f"  📄 {job['title']} @ {job['company']} ({job['salary']})")
            new_jobs.append(job)
            seen_ids.add(job["id"])

        time.sleep(delay)

    log.info(f"✅ 抓取完成，新增 {len(new_jobs)} 个岗位")
    return new_jobs
