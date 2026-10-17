from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock


SCHEMA_VERSION = 3
EXPORT_TABLES = (
    "subjects",
    "goals",
    "tasks",
    "knowledge_points",
    "study_sessions",
    "study_segments",
    "mistakes",
    "mistake_knowledge",
    "review_schedules",
    "review_events",
    "knowledge_reviews",
    "knowledge_review_events",
    "app_settings",
    "activity_events",
    "files",
    "mistake_files",
    "materials",
    "ai_runs",
    "schema_migrations",
)

REFERENCE_POINTS = {
    "基础工具": [
        "代数运算与因式分解",
        "函数、定义域与图像",
        "三角函数与常用恒等式",
        "指数与对数",
    ],
    "高等数学": [
        "数列与函数极限",
        "无穷小与等价替换",
        "函数连续性",
        "导数的定义与计算",
        "微分与导数应用",
        "不定积分与换元法",
        "定积分与基本定理",
        "多元函数与偏导数",
        "常微分方程初步",
    ],
    "线性代数": [
        "行列式",
        "矩阵运算",
        "向量与线性相关",
        "线性方程组",
        "特征值与特征向量",
    ],
    "概率统计": ["随机事件与概率", "随机变量与分布", "数学期望与方差"],
}


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.lock = RLock()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def transaction(self, write=False):
        self.lock.acquire()
        try:
            conn = self.connect()
        except Exception:
            self.lock.release()
            raise
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            self.lock.release()

    def initialize(self, timestamp: str):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            try:
                # Create private files before WAL/SHM inherit their permissions.
                import os

                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            # Migrations and their version marker commit atomically.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            current = conn.execute(
                "SELECT COALESCE(MAX(version),0) FROM schema_migrations"
            ).fetchone()[0]
            if current > SCHEMA_VERSION:
                raise RuntimeError("数据库版本比程序更新，请先升级程序。")
            if 0 < current < SCHEMA_VERSION:
                from datetime import datetime

                folder = self.path.parent / "backups"
                folder.mkdir(exist_ok=True, mode=0o700)
                backup_path = (
                    folder
                    / f"pre-migration-v{current}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}.sqlite3"
                )
                backup = sqlite3.connect(backup_path)
                try:
                    conn.backup(backup)
                finally:
                    backup.close()
                backup_path.chmod(0o600)
            for migration in sorted(
                (Path(__file__).parent / "migrations").glob("*.sql")
            ):
                version = int(migration.name.split("_")[0])
                if version <= current:
                    continue
                try:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    conn.executescript("BEGIN IMMEDIATE;\n" + migration.read_text())
                    conn.execute(
                        "INSERT INTO schema_migrations VALUES (?,?)",
                        (version, timestamp),
                    )
                    if version == 1:
                        for domain, titles in REFERENCE_POINTS.items():
                            conn.executemany(
                                "INSERT INTO knowledge_points(title,domain,is_reference,created_at,updated_at) VALUES (?,?,1,?,?)",
                                [
                                    (title, domain, timestamp, timestamp)
                                    for title in titles
                                ],
                            )
                    if conn.execute("PRAGMA foreign_key_check").fetchone():
                        raise RuntimeError("迁移关联检查失败，已回滚。")
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()


def rows(cursor):
    return [dict(row) for row in cursor.fetchall()]
