#!/usr/bin/env bash
# Preserve project-local libraries: upstream's wrapper resets LD_LIBRARY_PATH.
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
YANTU_ENGINE="${YANTU_WEBKIT_BUNDLE:?Playwright bundle path is required}/minibrowser-gtk"
for arg in "$@"; do
  if [[ "$arg" == '--headless' ]]; then
    YANTU_ENGINE="${YANTU_WEBKIT_BUNDLE}/minibrowser-wpe"
  fi
done
export WEBKIT_EXEC_PATH="$YANTU_ENGINE/bin"
export WEBKIT_INJECTED_BUNDLE_PATH="$YANTU_ENGINE/lib"
export WEBKIT_INSPECTOR_RESOURCES_PATH="$YANTU_ENGINE/share"
export WEBKIT_FORCE_COMPLEX_TEXT=1
export LD_LIBRARY_PATH="$YANTU_ROOT/.runtime/webkit-libs/usr/lib/x86_64-linux-gnu:$YANTU_ENGINE/lib:$YANTU_ENGINE/sys/lib:${LD_LIBRARY_PATH:-}"
exec "$YANTU_ENGINE/bin/MiniBrowser" "$@"
