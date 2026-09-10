@echo off
chcp 65001 >nul
rem 双击启动桌宠（Windows）。首次运行会自动建虚拟环境并装 PyQt6，需要联网。
cd /d "%~dp0.."

set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" ( where python >nul 2>&1 && set PY=python )
if "%PY%"=="" (
  echo 没找到 Python。请到 https://www.python.org/downloads/ 装 Python 3.9 以上，
  echo 安装时务必勾选 "Add python.exe to PATH"，然后重新双击本文件。
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo 首次运行：正在准备运行环境……
  %PY% -m venv .venv || ( echo 创建虚拟环境失败。 & pause & exit /b 1 )
)

.venv\Scripts\python.exe -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
  echo 正在安装 PyQt6（只有第一次需要）……
  .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check --upgrade pip >nul 2>&1
  .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check --only-binary=:all: PyQt6
  if errorlevel 1 (
    echo PyQt6 安装失败。国内网络可以试这条：
    echo   .venv\Scripts\python.exe -m pip install PyQt6 -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause & exit /b 1
  )
)

.venv\Scripts\python.exe tools\validate.py
if errorlevel 1 ( echo. & echo 配置检查没通过，先按上面的 ✗ 修一下。 & pause & exit /b 1 )

start "" .venv\Scripts\pythonw.exe app\main.py
echo 桌宠已启动，这个窗口可以关掉了。
timeout /t 3 >nul
exit /b 0
