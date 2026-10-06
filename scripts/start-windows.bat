@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
rem 双击启动桌宠（Windows）。需要 Python 3.10+；首次会安装 PyQt6 与 py-fsrs。
cd /d "%~dp0.."

set PY=
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
)
if not defined PY (
  where python >nul 2>&1 && python -c "import sys; raise SystemExit(sys.version_info < (3,10))" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo 没找到 Python 3.10 或更高版本。请到 https://www.python.org/downloads/ 安装，
  echo 安装时务必勾选 "Add python.exe to PATH"，然后重新双击本文件。
  pause & exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  set VENV_PREFIX=
  set VENV_PYOK=
  for /f "usebackq delims=" %%P in (`.venv\Scripts\python.exe -c "import sys; print(sys.prefix)" 2^>nul`) do set VENV_PREFIX=%%P
  .venv\Scripts\python.exe -c "import sys; raise SystemExit(sys.version_info ^< (3,10))" >nul 2>&1 && set VENV_PYOK=1
  if /I not "!VENV_PREFIX!"=="%CD%\.venv" ren .venv ".venv-incompatible-%RANDOM%"
  if not defined VENV_PYOK if exist ".venv\Scripts\python.exe" ren .venv ".venv-incompatible-%RANDOM%"
)
if not exist ".venv\Scripts\python.exe" (
  echo 首次运行：正在准备 Python 运行环境……
  %PY% -m venv .venv || ( echo 创建虚拟环境失败。 & pause & exit /b 1 )
  .venv\Scripts\python.exe -c "import sys; raise SystemExit(sys.version_info ^< (3,10))" >nul 2>&1 || ( echo 创建出的环境低于 Python 3.10。 & pause & exit /b 1 )
)

.venv\Scripts\python.exe -c "import PyQt6, fsrs; from importlib.metadata import version; assert version('fsrs') == '6.3.2'" >nul 2>&1
if errorlevel 1 (
  echo 正在安装运行依赖（只有第一次需要）……
  .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check --upgrade pip >nul 2>&1
  .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check --only-binary=:all: -r requirements.txt
  if errorlevel 1 (
    echo 依赖安装失败。国内网络可以试这条：
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause & exit /b 1
  )
)

.venv\Scripts\python.exe tools\validate.py
if errorlevel 1 ( echo. & echo 配置检查没通过，先按上面的 ✗ 修一下。 & pause & exit /b 1 )
start "" .venv\Scripts\pythonw.exe app\main.py
echo 桌宠已启动，这个窗口可以关掉了。
timeout /t 3 >nul
exit /b 0
