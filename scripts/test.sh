#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/toolchain.sh"
cd "$YANTU_ROOT"
.venv/bin/python -m pytest
cd frontend
pnpm build
"$YANTU_ROOT/.venv/bin/python" "$YANTU_ROOT/scripts/smoke_lifecycle.py"
pnpm test:e2e
