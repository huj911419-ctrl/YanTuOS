#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/toolchain.sh"
cd "$YANTU_ROOT"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r backend/requirements-dev.lock.txt
cd frontend
pnpm install --frozen-lockfile
echo '依赖已就绪。下一步运行 ./scripts/build.sh'
