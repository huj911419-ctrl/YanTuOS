#!/usr/bin/env bash
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$YANTU_ROOT/.venv/bin/python" "$YANTU_ROOT/scripts/manage.py" run
