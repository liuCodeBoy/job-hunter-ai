"""
crawl.py - Boss直聘岗位爬虫
使用 undetected-chromedriver 绕过反爬检测
"""

import time
import json
import re
import sys
import yaml
import logging
from pathlib import Path

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    print("请先安装依赖: pip install undetected-chromedriver selenium")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Boss直聘城市代码映射
CITY_CODE = {
    "全国": "100010000",
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "杭州": "101210100",
    "厦门": "101230200",
    "重庆": "101040100",
    "天津": "101030100",
    "长沙": "101250100",
}

# 薪资范围代码
SALARY_CODE = {
    (0, 0):    "",
    (0, 5):    "402",
    (5, 10):   "403",
    (10, 20):  "404",
    (20, 50):  "405",
    (50, 100): "406",
}


def get_salary_code(min_k: int, max_k: int) -> str:
    if min_k == 0 and max_k == 0:
        return ""
    if max_k <= 5:
        return "402"
    elif max_k <= 10:
        return "403"
    elif max_k <= 20:
        return "404"
    elif max_k <= 50:
        return "405"
    else:
        return "406"


def build_search_url(keyword: str, city: str, salary_min: int, salary_max: int,
                     experience: str, degree: str, page: int = 1) -> str:
    city_code = CITY_CODE.get(city, "101020100")
    salary_code = get_salary_code(salary_min, salary_max)

    exp_map = {"不限": "", "应届": "102", "1-3年": "103", "3-5年": "104", "5-10年": "105"}
    deg_map = {"不限": "", "大专": "203", "本科": "204", "硕士": "205", "博士": "206"}

    params = [
        f"query={keyword}",
        f"city={city_code}",
        f"page={page}",
    ]
    if salary_code:
        params.append(f"salary={salary_code}")
    exp_code = exp_map.get(experience, "")
    if exp_code:
        params.append(f"experience={exp_code}")
    deg_code = deg_map.get(degree, "")
    if deg_code:
        params.append(f"degree={deg_code}")

    return "https://www.zhipin.com/web/geek/job?" + "&".join(params)


def extract_job_id(url: str) -> str:
    """从 Boss直聘岗位 URL 提取唯一 ID"""
    match = re.search(r'/job_detail/([^/?]+)', url)
    return match.group(1) if match else url


def create_driver(headless: bool = True) -> uc.Chrome:
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=zh-CN")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = uc.Chrome(options=options)
    return driver


def wait_for_login(driver: uc.Chrome, timeout: int = 60):
    """检测是否需要登录，等待用户手动登录"""
    try:
        # 检查是否有登录弹窗
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dialog-container"))
        )
        log.warning("检测到登录弹窗，请在浏览器中手动登录（扫码或账号密码）...")
        log.warning(f"等待最多 {timeout} 秒...")
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "dialog-container"))
        )
        log.info("登录成功，继续抓取...")
        time.sleep(2)
    except TimeoutException:
        pass  # 没有登录弹窗，继续


def parse_job_list(driver: uc.Chrome, url: str, delay: float = 2) -> list:
    """解析岗位列表页，返回岗位基本信息列表"""
    jobs = []
    driver.get(url)
    time.sleep(delay)

    # 检查登录状态
    wait_for_login(driver)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "job-list-box"))
        )
    except TimeoutException:
        log.warning(f"页面加载超时或无岗位: {url}")
        return jobs

    # 滚动加载
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)

    job_cards = driver.find_elements(By.CSS_SELECTOR, ".job-list-box .job-card-wrapper")
    log.info(f"找到 {len(job_cards)} 个岗位卡片")

    for card in job_cards:
        try:
            title_el = card.find_element(By.CSS_SELECTOR, ".job-name")
            company_el = card.find_element(By.CSS_SELECTOR, ".company-name")
            salary_el = card.find_element(By.CSS_SELECTOR, ".salary")
            info_els = card.find_elements(By.CSS_SELECTOR, ".job-info .tag-list li")
            link_el = card.find_element(By.CSS_SELECTOR, "a.job-card-left")

            href = link_el.get_attribute("href") or ""
            job_id = extract_job_id(href)

            tags = [el.text.strip() for el in info_els]

            jobs.append({
                "id": job_id,
                "title": title_el.text.strip(),
                "company": company_el.text.strip(),
                "salary": salary_el.text.strip(),
                "tags": tags,
                "url": href,
            })
        except NoSuchElementException:
            continue

    return jobs


def parse_job_detail(driver: uc.Chrome, job: dict, delay: float = 2) -> dict:
    """抓取岗位详情页，补充 JD 描述"""
    if not job.get("url"):
        return job

    try:
        driver.get(job["url"])
        time.sleep(delay)

        # JD 描述
        try:
            desc_el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-detail-section"))
            )
            job["description"] = desc_el.text.strip()
        except TimeoutException:
            job["description"] = ""

        # 城市/经验/学历（从标签提取）
        try:
            req_els = driver.find_elements(By.CSS_SELECTOR, ".job-detail-info .info-primary p")
            for el in req_els:
                text = el.text.strip()
                if "年" in text or "经验" in text:
                    job["experience"] = text
                elif any(d in text for d in ["本科", "硕士", "大专", "博士", "学历"]):
                    job["degree"] = text
        except Exception:
            pass

        # 城市
        try:
            addr_el = driver.find_element(By.CSS_SELECTOR, ".job-detail-info .name")
            job["city"] = addr_el.text.strip()
        except Exception:
            pass

    except Exception as e:
        log.warning(f"抓取详情失败 {job['url']}: {e}")

    return job


def crawl(config: dict, db_path: str, seen_ids: set) -> list:
    """
    主爬虫入口
    返回新抓取的岗位列表（已过滤历史重复）
    """
    search = config["search"]
    crawler_cfg = config.get("crawler", {})
    headless = crawler_cfg.get("headless", True)
    delay = crawler_cfg.get("delay", 2)
    max_jobs = search.get("max_jobs", 20)

    driver = create_driver(headless=headless)
    new_jobs = []

    try:
        for keyword in search["keywords"]:
            if len(new_jobs) >= max_jobs:
                break

            log.info(f"搜索关键词: {keyword}")
            url = build_search_url(
                keyword=keyword,
                city=search.get("city", "上海"),
                salary_min=search.get("salary_min", 0),
                salary_max=search.get("salary_max", 0),
                experience=search.get("experience", "不限"),
                degree=search.get("degree", "不限"),
            )

            jobs = parse_job_list(driver, url, delay=delay)

            for job in jobs:
                if len(new_jobs) >= max_jobs:
                    break
                if job["id"] in seen_ids:
                    log.debug(f"跳过已见岗位: {job['title']} @ {job['company']}")
                    continue

                log.info(f"抓取详情: {job['title']} @ {job['company']}")
                job = parse_job_detail(driver, job, delay=delay)
                new_jobs.append(job)
                seen_ids.add(job["id"])

            time.sleep(delay)

    finally:
        driver.quit()

    log.info(f"本次共抓取 {len(new_jobs)} 个新岗位")
    return new_jobs


if __name__ == "__main__":
    # 单独测试爬虫
    cfg_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    if not cfg_path.exists():
        cfg_path = cfg_path.with_name("config.example.yaml")

    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    results = crawl(config, config["database"]["path"], set())
    print(json.dumps(results[:2], ensure_ascii=False, indent=2))
