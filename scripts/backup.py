#!/usr/bin/env python3
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
from manage import ROOT, load_env

sys.path.insert(0, str(ROOT / "backend"))
from app.db import Database
from app.services.backup import make_archive

parser = argparse.ArgumentParser(
    description="数据库与附件完整 ZIP 备份，不上传任何数据。"
)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
load_env()
path = Path(os.getenv("YANTU_DATABASE_PATH", str(ROOT / "data/yantu.sqlite3")))
if not path.is_absolute():
    path = ROOT / path
if not path.is_file():
    parser.exit(1, "数据库不存在，请先启动服务。\n")
out = (
    args.output
    or ROOT / "backups" / f"yantu-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
)
try:
    print("完整备份：", make_archive(Database(path), out))
except Exception as exc:
    parser.exit(1, "备份失败：" + str(exc) + "\n")
