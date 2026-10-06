#!/bin/zsh
# 双击启动桌宠（macOS）。需要 Python 3.10+；首次安装 PyQt6 与 py-fsrs，约 1-2 分钟。
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"

find_python() {
  for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c 'import sys; raise SystemExit(sys.version_info < (3,10))' >/dev/null 2>&1; then
      command -v "$cmd"; return 0
    fi
  done
  return 1
}
PYTHON="$(find_python)"
if [ -z "$PYTHON" ]; then
  echo "需要 Python 3.10 或更高版本。请从 https://www.python.org/downloads/ 安装后重试。"
  read -k 1; exit 1
fi

VENV_OK=false
if [ -x ".venv/bin/python" ]; then
  VENV_PREFIX="$(./.venv/bin/python -c 'import sys; print(sys.prefix)' 2>/dev/null)"
  if [ "$VENV_PREFIX" = "$ROOT/.venv" ] && ./.venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3,10))' >/dev/null 2>&1; then
    VENV_OK=true
  fi
fi
if [ "$VENV_OK" != true ]; then
  if [ -d .venv ]; then mv .venv ".venv-incompatible-$(date +%s)"; fi
  echo "首次运行：正在准备 Python 运行环境……"
  "$PYTHON" -m venv .venv || {
    echo "创建虚拟环境失败。请确认 Python 3.10+ 的 venv 功能可用。"
    read -k 1; exit 1; }
  ./.venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3,10))' || {
    echo "创建出的环境低于 Python 3.10，已停止。"; read -k 1; exit 1; }
fi

if ! ./.venv/bin/python -c "import PyQt6, fsrs; from importlib.metadata import version; assert version('fsrs') == '6.3.2'" >/dev/null 2>&1; then
  echo "正在安装运行依赖（只有第一次需要）……"
  ./.venv/bin/pip install --quiet --disable-pip-version-check --upgrade pip >/dev/null 2>&1
  ./.venv/bin/pip install --quiet --disable-pip-version-check --only-binary=:all: -r requirements.txt || {
    echo "依赖安装失败，请检查网络。国内网络可以试："
    echo "  ./.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
    read -k 1; exit 1; }
fi

if ! ./.venv/bin/python tools/validate.py; then
  echo ""; echo "配置检查没通过，先按上面的 ✗ 修一下。"; read -k 1; exit 1
fi

if pgrep -f "$ROOT/.venv/bin/python $ROOT/app/main.py" >/dev/null 2>&1 || pgrep -f "$ROOT/app/main.py" >/dev/null 2>&1; then
  echo "桌宠已经在运行了（右键桌宠可以退出）。"; exit 0
fi
nohup "$ROOT/.venv/bin/python" "$ROOT/app/main.py" >/dev/null 2>&1 &
echo "桌宠已启动，这个窗口可以关掉了。"
exit 0
