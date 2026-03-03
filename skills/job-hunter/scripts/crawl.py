"""
crawl.py - Boss直聘岗位爬虫
使用 Playwright 实现
支持平台：Windows / macOS / Linux（需要 Chrome 或 Chromium）
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
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("请先安装依赖: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Boss直聘城市代码映射
CITY_CODE = {
    "全国":  "100010000",
    "北京":  "101010100",
    "上海":  "101020100",
    "广州":  "101280100",
    "深圳":  "101280600",
    "杭州":  "101210100",
    "成都":  "101270100",
    "南京":  "101190100",
    "武汉":  "101200100",
    "西安":  "101110100",
    "苏州":  "101190400",
    "厦门":  "101230200",
    "重庆":  "101040100",
    "天津":  "101030100",
    "长沙":  "101250100",
}


def get_salary_code(min_k: int, max_k: int) -> str:
    if min_k == 0 and max_k == 0:
        return ""
    if max_k <= 5:   return "402"
    if max_k <= 10:  return "403"
    if max_k <= 20:  return "404"
    if max_k <= 50:  return "405"
    return "406"


def build_search_url(keyword: str, city: str, salary_min: int, salary_max: int,
                     experience: str, degree: str, page: int = 1) -> str:
    city_code = CITY_CODE.get(city, "101020100")
    salary_code = get_salary_code(salary_min, salary_max)
    exp_map = {"不限": "", "应届": "102", "1-3年": "103", "3-5年": "104", "5-10年": "105"}
    deg_map = {"不限": "", "大专": "203", "本科": "204", "硕士": "205", "博士": "206"}

    params = [f"query={keyword}", f"city={city_code}", f"page={page}"]
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
    match = re.search(r'/job_detail/([^/?\.]+)', url)
    return match.group(1) if match else re.sub(r'[^a-zA-Z0-9]', '_', url)[-32:]


def load_cookies(cookie_path: str) -> list:
    if not cookie_path or not os.path.exists(cookie_path):
        return []
    try:
        with open(cookie_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_cookies(context, cookie_path: str):
    try:
        cookies = context.cookies()
        os.makedirs(os.path.dirname(os.path.abspath(cookie_path)), exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        log.info(f"Cookie 已保存: {cookie_path}")
    except Exception as e:
        log.warning(f"保存 Cookie 失败: {e}")


def is_login_required(page) -> bool:
    """检测是否需要登录（检查是否有用户登录态标识）"""
    try:
        # 已登录则有用户头像或用户名
        page.wait_for_selector(
            ".nav-user-info, .user-nav, [class*='user-avatar'], .geek-nav",
            timeout=4000
        )
        return False  # 找到了，说明已登录
    except PWTimeout:
        return True   # 没找到，说明未登录


def wait_manual_login(page, context, cookie_path: str, timeout_sec: int = 180):
    """等待用户手动登录（扫码或账号密码）"""
    # 先跳转到登录页
    try:
        page.goto("https://www.zhipin.com/web/user/?ka=header-login", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
    except Exception:
        try:
            page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass

    log.warning("=" * 55)
    log.warning("⚠️  请在弹出的浏览器窗口中登录 Boss直聘")
    log.warning("   支持微信扫码 / 手机验证码 / 账号密码")
    log.warning(f"   登录完成后程序自动继续，等待 {timeout_sec} 秒")
    log.warning("=" * 55)
    try:
        page.wait_for_selector(
            ".nav-user-info, .user-nav, [class*='user-avatar'], .geek-nav, .user-info",
            timeout=timeout_sec * 1000
        )
        log.info("✅ 登录成功！正在保存 Cookie...")
        save_cookies(context, cookie_path)
        time.sleep(2)
    except PWTimeout:
        log.error("❌ 等待登录超时，请重新运行")
        raise RuntimeError("登录超时")


def handle_security_check(page, timeout_sec: int = 60):
    """检测并等待用户处理滑块验证"""
    if 'security' in page.url or 'passport' in page.url:
        log.warning("=" * 50)
        log.warning("⚠️  触发了 Boss直聘安全验证（滑块）")
        log.warning("   请在浏览器窗口中手动拖动滑块完成验证")
        log.warning(f"   等待最多 {timeout_sec} 秒...")
        log.warning("=" * 50)
        try:
            # 等待跳转回正常页面
            page.wait_for_url(
                lambda url: 'security' not in url and 'passport' not in url,
                timeout=timeout_sec * 1000
            )
            log.info("✅ 安全验证通过，继续抓取")
            time.sleep(2)
        except PWTimeout:
            log.error("❌ 安全验证超时，跳过本次搜索")


def parse_job_list(page, url: str, delay: float = 2) -> list:
    """解析岗位列表页"""
    jobs = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        # 被跳转到验证页面时 goto 会抛异常，检查当前 URL
        if 'security' in page.url or 'passport' in page.url:
            handle_security_check(page)
        else:
            log.warning(f"页面加载失败: {e}")
            return jobs

    # 检查是否在验证页面
    handle_security_check(page)
    time.sleep(delay)

    log.info(f"当前页面 URL: {page.url}")
    log.info(f"页面标题: {page.title()}")

    # 截图保存
    try:
        os.makedirs("data", exist_ok=True)
        page.screenshot(path="data/debug_screenshot.png")
        log.info("截图已保存: data/debug_screenshot.png")
    except Exception as e:
        log.warning(f"截图失败: {e}")

    # 检查是否跳转到验证页
    handle_security_check(page)

    # 先等岗位列表加载，再滚动
    try:
        page.wait_for_selector(".job-list-box", timeout=15000)
    except PWTimeout:
        log.warning(f"岗位列表未加载: {page.url}")
        # 截图保存方便排查
        try:
            os.makedirs("data", exist_ok=True)
            page.screenshot(path="data/debug_screenshot.png")
            log.info("已保存截图到 data/debug_screenshot.png")
        except Exception:
            pass
        return jobs

    # 滚动加载更多（页面稳定后）
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(0.8)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.8)
    except Exception:
        pass  # 滚动失败不影响已加载的数据

    cards = page.query_selector_all(".job-list-box .job-card-wrapper")
    log.info(f"找到 {len(cards)} 个岗位卡片")

    for card in cards:
        try:
            title_el  = card.query_selector(".job-name")
            company_el= card.query_selector(".company-name")
            salary_el = card.query_selector(".salary")
            link_el   = card.query_selector("a.job-card-left")
            if not all([title_el, company_el, salary_el, link_el]):
                continue

            href = link_el.get_attribute("href") or ""
            if not href.startswith("http"):
                href = "https://www.zhipin.com" + href

            tag_els = card.query_selector_all(".job-info .tag-list li")
            tags = [el.inner_text().strip() for el in tag_els]

            jobs.append({
                "id":          extract_job_id(href),
                "title":       title_el.inner_text().strip(),
                "company":     company_el.inner_text().strip(),
                "salary":      salary_el.inner_text().strip(),
                "tags":        tags,
                "url":         href,
                "experience":  tags[0] if len(tags) > 0 else "",
                "degree":      tags[1] if len(tags) > 1 else "",
                "city":        "",
                "description": "",
            })
        except Exception as e:
            log.debug(f"解析卡片异常: {e}")

    return jobs


def parse_job_detail(page, job: dict, delay: float = 2) -> dict:
    """抓取岗位详情页"""
    if not job.get("url"):
        return job
    try:
        page.goto(job["url"], wait_until="domcontentloaded", timeout=30000)
        time.sleep(delay)

        try:
            page.wait_for_selector(".job-detail-section", timeout=10000)
            desc_el = page.query_selector(".job-detail-section")
            job["description"] = desc_el.inner_text().strip() if desc_el else ""
        except PWTimeout:
            job["description"] = ""

        try:
            addr_el = page.query_selector(".job-detail-info .name")
            if addr_el:
                job["city"] = addr_el.inner_text().strip()
        except Exception:
            pass

    except Exception as e:
        log.warning(f"抓取详情失败 {job.get('url', '')}: {e}")
    return job


def crawl(config: dict, db_path: str, seen_ids: set) -> list:
    """主爬虫入口，返回新抓取的岗位列表"""
    search      = config["search"]
    crawler_cfg = config.get("crawler", {})
    headless    = crawler_cfg.get("headless", True)
    delay       = crawler_cfg.get("delay", 2)
    max_jobs    = search.get("max_jobs", 20)
    cookie_path = os.path.join(os.path.dirname(db_path), "cookies.json")

    new_jobs = []

    with sync_playwright() as p:
        # 首次尝试无头模式
        # 尝试使用系统 Chrome，回退到 Playwright 自带 Chromium
        import shutil
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
        ]
        chrome_bin = next((p for p in chrome_paths if shutil.os.path.exists(p)), None)
        launch_kwargs = dict(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        if chrome_bin:
            launch_kwargs["executable_path"] = chrome_bin
            log.info(f"使用系统 Chrome: {chrome_bin}")
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 加载已保存的 Cookie
        cookies = load_cookies(cookie_path)
        if cookies:
            context.add_cookies(cookies)
            log.info(f"已加载 {len(cookies)} 条历史 Cookie")

        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        # 访问首页检查登录状态
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded")
        time.sleep(3)

        if is_login_required(page) or not cookies:
            log.info("未检测到登录态，等待手动登录...")
            if headless:
                # 切换有头模式
                browser.close()
                browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="zh-CN",
                )
                if cookies:
                    context.add_cookies(cookies)
                page = context.new_page()
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                )
                page.goto("https://www.zhipin.com/", wait_until="domcontentloaded")
                time.sleep(2)

            wait_manual_login(page, context, cookie_path)

        # 登录后模拟正常用户行为：先在首页停留一会儿
        log.info("登录成功，预热中，请稍候...")
        page.goto("https://www.zhipin.com/", wait_until="domcontentloaded")
        time.sleep(3)
        # 随机滚动一下，模拟真实用户
        page.evaluate("window.scrollTo(0, 300)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(2)

        # ── 开始抓取 ──────────────────────────────────
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

            jobs = parse_job_list(page, url, delay=delay)

            for job in jobs:
                if len(new_jobs) >= max_jobs:
                    break
                if job["id"] in seen_ids:
                    continue

                log.info(f"📄 {job['title']} @ {job['company']} ({job['salary']})")
                job = parse_job_detail(page, job, delay=delay)
                new_jobs.append(job)
                seen_ids.add(job["id"])

            time.sleep(delay)

        # 保存最新 Cookie
        save_cookies(context, cookie_path)
        browser.close()

    log.info(f"✅ 本次抓取完成，新增 {len(new_jobs)} 个岗位")
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
