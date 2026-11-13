@echo off
chcp 65001 >nul
title 信息筛选官 - 一键设置
cd /d "%~dp0"

set "PY="
py -c "import sys" >nul 2>nul && set "PY=py"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
  echo [错误] 没找到可用的 Python 解释器。
  echo 请直接双击「信息筛选官.exe」，在页面里点「适配状态」→ 勾选后同意执行。
  pause
  exit /b 1
)

%PY% 一键设置.py
echo.
pause
