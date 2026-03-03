"""
db.py - SQLite 数据库操作
负责岗位去重、存储、查询历史
"""

import sqlite3
import os
from datetime import datetime


def get_conn(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    """初始化数据库表结构"""
    conn = get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,   -- Boss直聘岗位唯一ID
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            salary      TEXT,
            city        TEXT,
            experience  TEXT,
            degree      TEXT,
            description TEXT,
            url         TEXT,
            score       INTEGER DEFAULT 0,  -- 简历匹配分数 0-100
            analysis    TEXT,               -- AI 分析结果 JSON
            pushed      INTEGER DEFAULT 0,  -- 是否已推送
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS push_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id     TEXT NOT NULL,
            pushed_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def is_seen(db_path: str, job_id: str) -> bool:
    """判断岗位是否已抓取过"""
    conn = get_conn(db_path)
    row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return row is not None


def save_job(db_path: str, job: dict):
    """保存岗位信息"""
    conn = get_conn(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO jobs
            (id, title, company, salary, city, experience, degree, description, url, score, analysis, pushed, created_at)
        VALUES
            (:id, :title, :company, :salary, :city, :experience, :degree, :description, :url, :score, :analysis, :pushed, :created_at)
    """, {
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "salary": job.get("salary", ""),
        "city": job.get("city", ""),
        "experience": job.get("experience", ""),
        "degree": job.get("degree", ""),
        "description": job.get("description", ""),
        "url": job.get("url", ""),
        "score": job.get("score", 0),
        "analysis": job.get("analysis", ""),
        "pushed": 0,
        "created_at": datetime.now().isoformat(),
    })
    conn.commit()
    conn.close()


def update_analysis(db_path: str, job_id: str, score: int, analysis: str):
    """更新 AI 分析结果"""
    conn = get_conn(db_path)
    conn.execute(
        "UPDATE jobs SET score = ?, analysis = ? WHERE id = ?",
        (score, analysis, job_id)
    )
    conn.commit()
    conn.close()


def mark_pushed(db_path: str, job_id: str):
    """标记岗位已推送"""
    conn = get_conn(db_path)
    conn.execute("UPDATE jobs SET pushed = 1 WHERE id = ?", (job_id,))
    conn.execute(
        "INSERT INTO push_log (job_id, pushed_at) VALUES (?, ?)",
        (job_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_unpushed_jobs(db_path: str, min_score: int = 0, limit: int = 10) -> list:
    """获取未推送的岗位，按分数排序"""
    conn = get_conn(db_path)
    rows = conn.execute("""
        SELECT * FROM jobs
        WHERE pushed = 0 AND score >= ?
        ORDER BY score DESC, created_at DESC
        LIMIT ?
    """, (min_score, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(db_path: str) -> dict:
    """获取数据库统计信息"""
    conn = get_conn(db_path)
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    pushed = conn.execute("SELECT COUNT(*) FROM jobs WHERE pushed = 1").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE created_at >= date('now')"
    ).fetchone()[0]
    conn.close()
    return {"total": total, "pushed": pushed, "today_new": today}
