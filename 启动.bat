@echo off
chcp 65001 >nul
title 信息筛选官 - 本地原型
cd /d "%~dp0"

rem ---------- 找一个"真的能跑"的解释器 ----------
rem 注意：Windows 上的 python 命令可能是微软商店的占位程序，
rem where python 能找到它，但执行时什么都不输出。所以必须"执行一下"才算数。
set "PY="
py -c "import sys" >nul 2>nul && set "PY=py"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"

if not defined PY (
  echo.
  echo [错误] 没找到可用的 Python 解释器。
  echo.
  echo 你机器上可能只有微软商店的占位程序（执行后无任何输出）。
  echo 解决办法二选一：
  echo   1) 安装真实 Python: https://www.python.org/downloads/  （安装时勾选 Add python.exe to PATH）
  echo   2) 命令行执行: winget install Python.Python.3.12
  echo.
  pause
  exit /b 1
)

echo 使用解释器: %PY%
%PY% -V
echo.
echo 正在启动，浏览器稍后会自动打开 http://127.0.0.1:8000
echo 关闭这个窗口 = 停止程序。
echo.
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
%PY% app.py
pause
