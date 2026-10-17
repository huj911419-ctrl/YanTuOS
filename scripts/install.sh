#!/usr/bin/env bash
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$YANTU_ROOT/scripts/setup.sh"
"$YANTU_ROOT/scripts/build.sh"
echo '安装与构建完成。运行 ./scripts/start.sh 即可打开学习空间。'
