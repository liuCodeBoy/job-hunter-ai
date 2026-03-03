"""
main.py - 主入口
串联爬虫 → 分析 → 存储 → 推送 完整流程
"""

import sys
import yaml
import logging
import argparse
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, is_seen, save_job, update_analysis, mark_pushed, get_unpushed_jobs, get_stats
from crawl import crawl
from analyze import batch_analyze
from push import push_jobs, push_summary

import os as _os
_os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/job-hunter.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        # 尝试找 config.example.yaml
        example = path.parent / "config.example.yaml"
        if example.exists():
            log.warning(f"config.yaml 不存在，使用示例配置: {example}")
            path = example
        else:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(config_path: str, skip_crawl: bool = False, skip_push: bool = False):
    """完整运行一次求职助手"""
    config = load_config(config_path)
    db_path = config["database"]["path"]

    # 初始化数据库
    init_db(db_path)
    log.info("=== 求职助手启动 ===")

    # ── Step 1: 爬虫 ──────────────────────────────
    if not skip_crawl:
        log.info("Step 1/3: 开始抓取 Boss直聘岗位...")

        # 获取已知的岗位 ID（去重用）
        from db import get_conn
        conn = get_conn(db_path)
        seen_ids = set(
            row[0] for row in conn.execute("SELECT id FROM jobs").fetchall()
        )
        # 检查每日限额
        today_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE created_at >= date('now')"
        ).fetchone()[0]
        conn.close()

        daily_limit = config.get("search", {}).get("daily_limit", 30)
        if today_count >= daily_limit:
            log.warning(f"今日已抓取 {today_count} 个岗位，达到每日上限 {daily_limit}，跳过抓取")
            new_jobs = []
        else:
            # 动态调整本次最大抓取数，不超过每日限额
            remaining = daily_limit - today_count
            config["search"]["max_jobs"] = min(
                config["search"].get("max_jobs", 15), remaining
            )
            log.info(f"今日已抓取 {today_count} 个，本次最多抓 {config['search']['max_jobs']} 个")
            new_jobs = crawl(config, db_path, seen_ids)
            log.info(f"抓取完成，新增 {len(new_jobs)} 个岗位")

        if not new_jobs:
            log.info("没有新岗位，退出")
            push_summary("今日没有发现新岗位，明天继续加油！", config)
            return
    else:
        log.info("Step 1/3: 跳过爬虫（--skip-crawl）")
        new_jobs = []

    # ── Step 2: AI 分析 ───────────────────────────
    log.info("Step 2/3: AI 分析岗位...")
    resume_path = config.get("resume", {}).get("path", "resume.md")
    analyzed_jobs = batch_analyze(new_jobs, resume_path)

    # 保存到数据库
    for job in analyzed_jobs:
        save_job(db_path, job)
    log.info(f"已保存 {len(analyzed_jobs)} 个岗位到数据库")

    # ── Step 3: 推送 ──────────────────────────────
    if not skip_push:
        log.info("Step 3/3: 推送到微信...")
        push_cfg = config.get("push", {})
        min_score = push_cfg.get("min_score", 0)
        max_push = push_cfg.get("max_push", 10)

        jobs_to_push = get_unpushed_jobs(db_path, min_score=min_score, limit=max_push)
        stats = get_stats(db_path)

        if jobs_to_push:
            success = push_jobs(jobs_to_push, config, stats)
            if success:
                for job in jobs_to_push:
                    mark_pushed(db_path, job["id"])
                log.info(f"成功推送 {len(jobs_to_push)} 个岗位")
            else:
                log.error("推送失败")
        else:
            log.info(f"没有符合条件的岗位（最低分数: {min_score}）")
    else:
        log.info("Step 3/3: 跳过推送（--skip-push）")

    log.info("=== 求职助手运行完毕 ===")
    stats = get_stats(db_path)
    log.info(f"数据库统计: 累计 {stats['total']} 个岗位，已推送 {stats['pushed']} 个，今日新增 {stats['today_new']} 个")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="job-hunter-ai 求职助手")
    parser.add_argument(
        "--config", default="config.yaml",
        help="配置文件路径（默认: config.yaml）"
    )
    parser.add_argument(
        "--skip-crawl", action="store_true",
        help="跳过爬虫，直接分析+推送已有岗位"
    )
    parser.add_argument(
        "--skip-push", action="store_true",
        help="跳过推送，只爬取+分析"
    )
    args = parser.parse_args()

    run(
        config_path=args.config,
        skip_crawl=args.skip_crawl,
        skip_push=args.skip_push,
    )
