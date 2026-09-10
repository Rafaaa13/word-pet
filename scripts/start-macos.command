#!/bin/zsh
# 双击启动桌宠（macOS）。首次运行会自动建虚拟环境并装 PyQt6，需要联网，约 1-2 分钟。
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"

if [ ! -x ".venv/bin/python" ]; then
  echo "首次运行：正在准备运行环境……"
  /usr/bin/env python3 -m venv .venv || {
    echo "创建虚拟环境失败。请先在终端里运行：xcode-select --install"
    echo "装完命令行工具后再双击本文件。"; read -k 1; exit 1; }
fi

if ! ./.venv/bin/python -c "import PyQt6" >/dev/null 2>&1; then
  echo "正在安装 PyQt6（只有第一次需要）……"
  ./.venv/bin/pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1
  ./.venv/bin/pip install --quiet --disable-pip-version-check --only-binary=:all: PyQt6 || {
    echo "PyQt6 安装失败，检查网络后重新双击。国内网络可以试："
    echo "  ./.venv/bin/pip install PyQt6 -i https://pypi.tuna.tsinghua.edu.cn/simple"
    read -k 1; exit 1; }
fi

if ! ./.venv/bin/python tools/validate.py; then
  echo ""
  echo "配置检查没通过，先按上面的 ✗ 修一下。"
  read -k 1; exit 1
fi

if pgrep -f "$ROOT/app/main.py" >/dev/null 2>&1; then
  echo "桌宠已经在运行了（右键桌宠可以退出）。"; exit 0
fi

nohup ./.venv/bin/python app/main.py >/dev/null 2>&1 &
echo "桌宠已启动，这个窗口可以关掉了。"
exit 0
