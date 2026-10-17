#!/usr/bin/env bash
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$YANTU_ROOT/.venv/bin/python" ]]; then echo '请先运行 ./scripts/setup.sh' >&2; exit 1; fi
exec "$YANTU_ROOT/.venv/bin/python" "$YANTU_ROOT/scripts/manage.py" start
