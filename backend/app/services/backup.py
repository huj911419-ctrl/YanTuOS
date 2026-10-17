"""Local, versioned, verifiable archives. Restore is staged and preserves a rollback archive."""

from datetime import datetime, timezone
import hashlib
import os
from functools import lru_cache
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from ..db import Database, EXPORT_TABLES, SCHEMA_VERSION

MAX_ARCHIVE = 512 * 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def schema_signature(conn):
    return {
        name: re.sub(r"\s+", "", sql).lower()
        for name, sql in conn.execute(
            "SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
        )
    }


@lru_cache(maxsize=1)
def expected_schema():
    with tempfile.TemporaryDirectory(prefix="yantu-schema-") as folder:
        db = Database(Path(folder) / "reference.sqlite3")
        db.initialize(datetime.now(timezone.utc).isoformat())
        with db.transaction() as conn:
            return schema_signature(conn)


def validate_database(path):
    c = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        c.execute("PRAGMA trusted_schema=OFF")
        if (
            c.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or c.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise ValueError("数据库完整性或关联校验失败。")
        tables = {
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not {
            "tasks",
            "knowledge_points",
            "study_sessions",
            "study_segments",
            "mistakes",
            "mistake_knowledge",
            "review_schedules",
            "review_events",
            "schema_migrations",
        }.issubset(tables):
            raise ValueError("不是完整的研途数据库。")
        if tables - set(EXPORT_TABLES):
            raise ValueError("数据库包含未知表。")
        if c.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN('trigger','view')"
        ).fetchone():
            raise ValueError("备份包含不受支持的视图或触发器。")
        version = c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if version not in range(1, SCHEMA_VERSION + 1):
            raise ValueError("备份版本不受支持，请升级程序。")
        if version == SCHEMA_VERSION and schema_signature(c) != expected_schema():
            raise ValueError("数据库表结构与版本不匹配，拒绝恢复。")
        return version
    finally:
        c.close()


def validate_files(dbfile, folder):
    with sqlite3.connect(dbfile) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='files'").fetchone():
            return
        for ident, size, checksum in c.execute("SELECT id,size,sha256 FROM files"):
            if not re.fullmatch(r"[0-9a-f]{32}", ident):
                raise ValueError("附件标识不合法。")
            f = folder / ident
            if (
                not f.is_file()
                or f.is_symlink()
                or f.stat().st_size != size
                or sha(f) != checksum
            ):
                raise ValueError(
                    "附件缺失或校验失败；含附件的数据请使用完整 ZIP 备份恢复。"
                )


def make_archive(db, output):
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.exists():
        raise ValueError("备份目标已存在。")
    with (
        db.transaction(write=True),
        tempfile.TemporaryDirectory(prefix="yantu-backup-") as temp,
    ):
        snapshot = Path(temp) / "database.sqlite3"
        source = db.connect()
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            source.close()
            target.close()
        validate_files(snapshot, db.path.parent / "uploads")
        checks = {"database.sqlite3": sha(snapshot)}
        fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with (
            os.fdopen(fd, "wb") as binary,
            zipfile.ZipFile(binary, "w", compression=zipfile.ZIP_DEFLATED) as z,
        ):
            z.write(snapshot, "database.sqlite3")
            with sqlite3.connect(snapshot) as c:
                for (ident,) in c.execute("SELECT id FROM files"):
                    f = db.path.parent / "uploads" / ident
                    checks["uploads/" + ident] = sha(f)
                    z.write(f, "uploads/" + ident)
            z.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format": "yantu-os-backup",
                        "version": 1,
                        "schema_version": SCHEMA_VERSION,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "sha256": checks,
                    },
                    ensure_ascii=False,
                ),
            )
        output.chmod(0o600)
    return output


def from_json(payload, dbfile):
    if not isinstance(payload, dict):
        raise ValueError("JSON 顶层必须是研途导出对象。")
    if (
        payload.get("format") != "yantu-os"
        or payload.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError("JSON 格式或版本不匹配；旧版数据请使用 SQLite/ZIP 恢复。")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(EXPORT_TABLES):
        raise ValueError("JSON 表集合不完整。")
    database = Database(dbfile)
    database.initialize(datetime.now(timezone.utc).isoformat())
    c = database.connect()
    try:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("BEGIN IMMEDIATE")
        for name in EXPORT_TABLES:
            c.execute(f"DELETE FROM {name}")
        for name, records in tables.items():
            allowed = {r[1] for r in c.execute(f"PRAGMA table_info({name})")}
            if not isinstance(records, list) or len(records) > 1_000_000:
                raise ValueError("JSON 记录格式或数量异常。")
            for record in records:
                if not isinstance(record, dict) or set(record) != allowed:
                    raise ValueError(f"{name} 字段不匹配。")
                keys = list(record)
                c.execute(
                    f"INSERT INTO {name} ("
                    + ",".join(keys)
                    + ") VALUES ("
                    + ",".join("?" for _ in keys)
                    + ")",
                    tuple(record[k] for k in keys),
                )
        if c.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("JSON 关联数据不完整。")
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def is_sqlite(source):
    with source.open("rb") as f:
        return f.read(16) == b"SQLite format 3\x00"


def prepare_restore(source, output):
    """output must be NEW; failure never touches the live data directory."""
    if output.exists():
        raise ValueError("恢复目标已存在，拒绝覆盖。")
    output.mkdir(parents=True, mode=0o700)
    (output / "uploads").mkdir(mode=0o700)
    target = output / "yantu.sqlite3"
    try:
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as z:
                infos = z.infolist()
                if len(infos) > 100000 or sum(i.file_size for i in infos) > MAX_ARCHIVE:
                    raise ValueError("备份展开后超过 512 MB 限制。")
                names = [i.filename for i in infos]
                if len(names) != len(set(names)) or "manifest.json" not in names:
                    raise ValueError("备份清单异常。")
                if z.getinfo("manifest.json").file_size > 2_000_000:
                    raise ValueError("备份清单过大。")
                if (
                    sum(i.file_size for i in infos)
                    > shutil.disk_usage(output).free - 50_000_000
                ):
                    raise ValueError("磁盘剩余空间不足以安全恢复。")
                manifest = json.loads(z.read("manifest.json"))
                if not isinstance(manifest, dict):
                    raise ValueError("备份清单格式错误。")
                if (
                    manifest.get("format") != "yantu-os-backup"
                    or manifest.get("version") != 1
                ):
                    raise ValueError("不支持的备份格式。")
                hashes = manifest.get("sha256", {})
                if not isinstance(hashes, dict):
                    raise ValueError("备份校验清单格式错误。")
                if (
                    set(names) != set(hashes) | {"manifest.json"}
                    or "database.sqlite3" not in hashes
                ):
                    raise ValueError("备份文件清单不一致。")
                for name, checksum in hashes.items():
                    if name != "database.sqlite3" and not re.fullmatch(
                        r"uploads/[0-9a-f]{32}", name
                    ):
                        raise ValueError("备份包含危险或未知路径。")
                    dest = target if name == "database.sqlite3" else output / name
                    with z.open(name) as inp, dest.open("xb") as out:
                        shutil.copyfileobj(inp, out)
                    dest.chmod(0o600)
                    if sha(dest) != checksum:
                        raise ValueError("备份文件校验和不匹配。")
        elif is_sqlite(source):
            shutil.copyfile(source, target)
            target.chmod(0o600)
        else:
            if source.stat().st_size > 64 * 1024 * 1024:
                raise ValueError("JSON 导入最大 64 MB。")
            from_json(json.loads(source.read_text()), target)
        validate_database(target)
        Database(target).initialize(datetime.now(timezone.utc).isoformat())
        validate_database(target)
        validate_files(target, output / "uploads")
        with sqlite3.connect(target) as c:
            counts = {
                table: c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in EXPORT_TABLES
            }
        return {"counts": counts, "schema_version": SCHEMA_VERSION}
    except Exception:
        # Only removes the newly created, isolated failed staging directory.
        shutil.rmtree(output)
        raise


def copy_database(source, target):
    src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def recover_pending_restore(db):
    """If interrupted at any point, startup deterministically restores the pre-change archive."""
    marker = db.path.parent / "restore-in-progress.json"
    if not marker.exists():
        return False
    with db.lock:
        info = json.loads(marker.read_text())
        backup = Path(info["backup"])
        if not backup.resolve().is_relative_to((db.path.parent / "backups").resolve()):
            raise ValueError("恢复日志中的备份路径异常，请人工检查。")
        recovered = db.path.parent / ("recovery-" + uuid.uuid4().hex)
        prepare_restore(backup, recovered)
        live = db.path.parent / "uploads"
        if live.exists():
            live.rename(db.path.parent / ("uploads-interrupted-" + uuid.uuid4().hex))
        (recovered / "uploads").rename(live)
        copy_database(recovered / "yantu.sqlite3", db.path)
        marker.unlink()
        return True


def activate_restore(db, staging):
    with db.lock:
        validate_database(staging / "yantu.sqlite3")
        validate_files(staging / "yantu.sqlite3", staging / "uploads")
        ident = uuid.uuid4().hex
        backup = make_archive(
            db, db.path.parent / "backups" / f"before-restore-{ident}.zip"
        )
        marker = db.path.parent / "restore-in-progress.json"
        with marker.open("x") as f:
            json.dump({"backup": str(backup.resolve())}, f)
            f.flush()
            os.fsync(f.fileno())
        marker.chmod(0o600)
        live = db.path.parent / "uploads"
        old = db.path.parent / f"uploads-before-{ident}"
        try:
            if live.exists():
                live.rename(old)
            (staging / "uploads").rename(live)
            copy_database(staging / "yantu.sqlite3", db.path)
        except Exception:
            recover_pending_restore(db)
            raise
        marker.unlink()
        return {
            "restored": True,
            "rollback_backup": str(backup),
            "preserved_uploads": str(old),
        }
