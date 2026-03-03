"""
crawl.py - Boss直聘岗位爬虫
使用 undetected-chromedriver 绕过自动化检测
"""

import os
import re
import sys
import time
import json
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
    print("请先安装: pip install undetected-chromedriver selenium")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CITY_CODE = {
    "全国": "100010000", "北京": "101010100", "上海": "101020100",
    "广州": "101280100", "深圳": "101280600", "杭州": "101210100",
    "成都": "101270100", "南京": "101190100", "武汉": "101200100",
    "西安": "101110100", "苏州": "101190400", "厦门": "101230200",
    "重庆": "101040100", "天津": "101030100", "长沙": "101250100",
}


def get_salary_code(min_k, max_k):
    if min_k == 0 and max_k == 0: return ""
    if max_k <= 5:  return "402"
    if max_k <= 10: return "403"
    if max_k <= 20: return "404"
    if max_k <= 50: return "405"
    return "406"


def build_search_url(keyword, city, salary_min, salary_max, experience, degree, page=1):
    city_code = CITY_CODE.get(city, "101020100")
    salary_code = get_salary_code(salary_min, salary_max)
    exp_map = {"不限": "", "应届": "102", "1-3年": "103", "3-5年": "104", "5-10年": "105"}
    deg_map = {"不限": "", "大专": "203", "本科": "204", "硕士": "205", "博士": "206"}
    params = [f"query={keyword}", f"city={city_code}", f"page={page}"]
    if salary_code: params.append(f"salary={salary_code}")
    if exp_map.get(experience): params.append(f"experience={exp_map[experience]}")
    if deg_map.get(degree): params.append(f"degree={deg_map[degree]}")
    return "https://www.zhipin.com/web/geek/job?" + "&".join(params)


def extract_job_id(url):
    match = re.search(r'/job_detail/([^/?\.]+)', url)
    return match.group(1) if match else re.sub(r'[^a-zA-Z0-9]', '_', url)[-32:]


def load_cookies(cookie_path):
    if not cookie_path or not os.path.exists(cookie_path):
        return []
    try:
        with open(cookie_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_cookies(driver, cookie_path):
    try:
        cookies = driver.get_cookies()
        os.makedirs(os.path.dirname(os.path.abspath(cookie_path)), exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        log.info(f"Cookie 已保存: {cookie_path}")
    except Exception as e:
        log.warning(f"保存 Cookie 失败: {e}")


def create_driver(headless=False):
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,800")
    options.add_argument("--lang=zh-CN")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # undetected_chromedriver 不支持真正的 headless（会被检测），始终用有头模式
    driver = uc.Chrome(options=options, headless=False)
    return driver


def is_logged_in(driver):
    """检测是否已登录"""
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                ".nav-user-info, .user-nav, .geek-nav, [class*='user-avatar']"))
        )
        return True
    except TimeoutException:
        return False


def wait_login(driver, cookie_path, timeout=180):
    """等待用户手动登录"""
    driver.get("https://www.zhipin.com/web/user/?ka=header-login")
    time.sleep(2)
    log.warning("=" * 55)
    log.warning("⚠️  请在浏览器窗口中登录 Boss直聘")
    log.warning("   微信扫码 / 手机验证码 / 账号密码 均可")
    log.warning(f"   登录完成后程序自动继续（等待 {timeout} 秒）")
    log.warning("=" * 55)
    end = time.time() + timeout
    while time.time() < end:
        if is_logged_in(driver):
            log.info("✅ 登录成功！")
            save_cookies(driver, cookie_path)
            time.sleep(2)
            return
        time.sleep(2)
    raise RuntimeError("登录超时，请重新运行")


def apply_cookies(driver, cookies):
    """注入已保存的 Cookie"""
    driver.get("https://www.zhipin.com/")
    time.sleep(2)
    for ck in cookies:
        try:
            driver.add_cookie({k: ck[k] for k in ('name','value','domain','path') if k in ck})
        except Exception:
            pass
    driver.refresh()
    time.sleep(3)


def warmup(driver):
    """登录后模拟正常用户行为，减少风控"""
    log.info("预热中（模拟正常浏览）...")
    driver.get("https://www.zhipin.com/")
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, 400)")
    time.sleep(1.5)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(2)


def parse_job_list(driver, url, delay=3):
    """解析岗位列表页"""
    jobs = []
    driver.get(url)
    time.sleep(delay)

    # 截图调试
    try:
        os.makedirs("data", exist_ok=True)
        driver.save_screenshot("data/debug_screenshot.png")
    except Exception:
        pass

    log.info(f"当前URL: {driver.current_url[:80]}")

    # 检查是否被跳转到风控/登录页
    if any(x in driver.current_url for x in ['security', 'passport', 'login']):
        log.warning("触发风控或需要登录，跳过本次搜索")
        return jobs

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".job-list-box"))
        )
    except TimeoutException:
        log.warning(f"岗位列表未加载: {driver.current_url[:80]}")
        return jobs

    # 滚动加载
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
    except Exception:
        pass

    cards = driver.find_elements(By.CSS_SELECTOR, ".job-list-box .job-card-wrapper")
    log.info(f"找到 {len(cards)} 个岗位")

    for card in cards:
        try:
            title   = card.find_element(By.CSS_SELECTOR, ".job-name").text.strip()
            company = card.find_element(By.CSS_SELECTOR, ".company-name").text.strip()
            salary  = card.find_element(By.CSS_SELECTOR, ".salary").text.strip()
            link    = card.find_element(By.CSS_SELECTOR, "a.job-card-left")
            href    = link.get_attribute("href") or ""
            if not href.startswith("http"):
                href = "https://www.zhipin.com" + href

            tags = [el.text.strip() for el in card.find_elements(By.CSS_SELECTOR, ".job-info .tag-list li")]

            jobs.append({
                "id": extract_job_id(href),
                "title": title, "company": company, "salary": salary,
                "url": href, "tags": tags,
                "experience": tags[0] if len(tags) > 0 else "",
                "degree":     tags[1] if len(tags) > 1 else "",
                "city": "", "description": "",
            })
        except NoSuchElementException:
            continue

    return jobs


def parse_job_detail(driver, job, delay=2):
    """抓取岗位详情"""
    if not job.get("url"):
        return job
    try:
        driver.get(job["url"])
        time.sleep(delay)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-detail-section"))
            )
            job["description"] = driver.find_element(By.CSS_SELECTOR, ".job-detail-section").text.strip()
        except TimeoutException:
            job["description"] = ""
        try:
            job["city"] = driver.find_element(By.CSS_SELECTOR, ".job-detail-info .name").text.strip()
        except Exception:
            pass
    except Exception as e:
        log.warning(f"详情抓取失败: {e}")
    return job


def crawl(config, db_path, seen_ids):
    search      = config["search"]
    crawler_cfg = config.get("crawler", {})
    delay       = crawler_cfg.get("delay", 3)
    max_jobs    = search.get("max_jobs", 15)
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), "cookies.json")

    new_jobs = []
    driver = create_driver()

    try:
        cookies = load_cookies(cookie_path)

        if cookies:
            log.info(f"加载 {len(cookies)} 条历史 Cookie...")
            apply_cookies(driver, cookies)
            if not is_logged_in(driver):
                log.info("Cookie 已过期，需要重新登录")
                wait_login(driver, cookie_path)
            else:
                log.info("✅ Cookie 有效，已自动登录")
        else:
            wait_login(driver, cookie_path)

        warmup(driver)

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

            jobs = parse_job_list(driver, url, delay=delay)

            for job in jobs:
                if len(new_jobs) >= max_jobs:
                    break
                if job["id"] in seen_ids:
                    continue
                log.info(f"📄 {job['title']} @ {job['company']} ({job['salary']})")
                job = parse_job_detail(driver, job, delay=delay)
                new_jobs.append(job)
                seen_ids.add(job["id"])

            time.sleep(delay)

        save_cookies(driver, cookie_path)

    finally:
        driver.quit()

    log.info(f"✅ 抓取完成，新增 {len(new_jobs)} 个岗位")
    return new_jobs


if __name__ == "__main__":
    cfg_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
    if not cfg_path.exists():
        cfg_path = cfg_path.with_name("config.example.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    os.makedirs("data", exist_ok=True)
    results = crawl(config, config["database"]["path"], set())
    print(json.dumps(results[:2], ensure_ascii=False, indent=2))
