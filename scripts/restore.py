#!/usr/bin/env python3
"""Restore a backup into a NEW database. Existing files are never overwritten."""

import argparse
from pathlib import Path
import sqlite3
import os

REQUIRED = {
    "tasks",
    "knowledge_points",
    "study_sessions",
    "study_segments",
    "mistakes",
    "mistake_knowledge",
    "review_schedules",
    "review_events",
    "schema_migrations",
}


def restore(source: Path, output: Path):
    if not source.is_file():
        raise ValueError("备份文件不存在。")
    if output.exists():
        raise ValueError("目标文件已存在，为防止丢失学习数据，拒绝覆盖。")
    conn = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("备份完整性检查失败。")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not REQUIRED.issubset(tables):
            raise ValueError("这不是研途 OS 的完整备份。")
        if conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
            0
        ] not in (1, 2, 3):
            raise ValueError("备份版本不受当前程序支持。")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("备份关联数据校验失败。")
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents accidental overwrites even in a race.
        fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        target = sqlite3.connect(output)
        try:
            conn.backup(target)
        finally:
            target.close()
        output.chmod(0o600)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        restore(args.source, args.output)
    except (ValueError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"恢复失败：{exc}\n")
    print(f"已恢复到 {args.output.resolve()}。原数据库未修改。")
