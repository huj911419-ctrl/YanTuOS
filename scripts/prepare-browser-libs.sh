#!/usr/bin/env bash
# Optional Ubuntu 26.04 x86_64 test dependencies, extracted without sudo/install.
set -euo pipefail
YANTU_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -m)" != 'x86_64' ]] || ! rg -q '^VERSION_ID="26.04"' /etc/os-release; then
  echo '此辅助脚本仅用于 Ubuntu 26.04 x86_64。其他系统请按 Playwright 官方要求准备浏览器依赖。' >&2
  exit 1
fi
mkdir -p "$YANTU_ROOT/.runtime/webkit-libs/debs"
cd "$YANTU_ROOT/.runtime/webkit-libs/debs"
apt download libevent-2.1-7t64 libflite1 libavif16 libmanette-0.2-0 \
  libbacktrace0 libyuv0 libdav1d7 libgav1-2 libhidapi-hidraw0 libx264-165
for package in ./*.deb; do dpkg-deb --extract "$package" ..; done
echo '测试依赖已解包到项目 .runtime/，未安装或修改任何系统包。'
