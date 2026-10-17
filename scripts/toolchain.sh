#!/usr/bin/env bash
# Shared detection; never modifies the user's shell or system installation.
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
YANTU_BUNDLE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if ! command -v node >/dev/null 2>&1 && [[ -x "$YANTU_BUNDLE/node/bin/node" ]]; then
  export PATH="$YANTU_BUNDLE/node/bin:$PATH"
fi
if ! command -v pnpm >/dev/null 2>&1 && [[ -x "$YANTU_BUNDLE/bin/fallback/pnpm" ]]; then
  export PATH="$YANTU_BUNDLE/bin/fallback:$PATH"
fi
if ! command -v node >/dev/null 2>&1 || ! command -v pnpm >/dev/null 2>&1; then
  echo '需要 Node.js 22.12+ 和 pnpm 11.25。安装后重新运行；现有构建可直接用 start.sh 启动。' >&2
  exit 1
fi
node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<12)){console.error("需要 Node.js 22.12+");process.exit(1)}'
