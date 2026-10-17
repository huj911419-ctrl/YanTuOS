#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.backup import prepare_restore

parser = argparse.ArgumentParser(
    description="将 ZIP/SQLite/JSON 恢复到全新目录；已有目录不会覆盖。"
)
parser.add_argument("source", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
try:
    result = prepare_restore(args.source, args.output)
    print("隔离恢复通过：", args.output.resolve())
    print("记录数量：", result["counts"])
    print(
        "原数据未改变。可设置 YANTU_DATABASE_PATH 指向新目录中的 yantu.sqlite3 后启动。"
    )
except Exception as exc:
    parser.exit(1, "恢复失败：" + str(exc) + "\n")
