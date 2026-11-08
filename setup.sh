#!/usr/bin/env bash
# diagram_mcp 安装：Node 依赖、Playwright Chromium、固定版本 PlantUML jar。
# 用法: bash setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

JAR_VERSION="1.2026.9"
JAR_URL="https://github.com/plantuml/plantuml/releases/download/v${JAR_VERSION}/plantuml-${JAR_VERSION}.jar"
JAR_PATH="$ROOT/vendor/plantuml.jar"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少 $1。$2" >&2
    exit 1
  fi
}

need node "请安装 Node.js 20+。"
need java "请安装 JRE 17+。PlantUML 不需要 Graphviz，序列图和类图由 jar 直接渲染。"
need npm "请安装 npm。"

echo "[1/3] 安装 mermaid、playwright、roughjs、jsdom"
npm install --no-audit --no-fund

echo "[2/3] 安装 Playwright Chromium"
npx playwright install chromium

echo "[3/3] 准备 PlantUML ${JAR_VERSION}"
mkdir -p "$ROOT/vendor"
if [[ ! -f "$JAR_PATH" ]]; then
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$JAR_PATH" "$JAR_URL"
  else
    python3 - "$JAR_URL" "$JAR_PATH" <<'PY'
import sys
import urllib.request
urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
PY
  fi
fi

python3 - <<'PY'
from diagram_mcp.constants import Meta
print(f"[OK] {Meta.name} v{Meta.version}")
PY

echo
echo "安装完成。在本目录启动："
echo "  python3 -m diagram_mcp"
echo "MCP 客户端示例见 README.md。"
