@echo off
chcp 65001 >nul
title 打包 信息筛选官.exe
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [错误] 没找到 py 启动器，请先安装 Python 3.9+。
  pause
  exit /b 1
)

echo [1/3] 安装打包工具 PyInstaller（已装会跳过）...
py -m pip install --disable-pip-version-check pyinstaller
if errorlevel 1 (
  echo [错误] PyInstaller 安装失败，检查网络。
  pause
  exit /b 1
)

set "ICONARG="
if exist "app.ico" set "ICONARG=--icon app.ico"

echo [2/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist InfoFilter.spec del /q InfoFilter.spec

echo [3/3] 打包中（约 1 分钟）...
py -m PyInstaller --noconfirm --clean --onefile --noconsole ^
  --name InfoFilter %ICONARG% ^
  --add-data "index.html;." ^
  --add-data "samples.json;." ^
  app.py
if not exist "dist\InfoFilter.exe" (
  echo [错误] 打包失败，看上面的报错。
  pause
  exit /b 1
)

copy /Y "dist\InfoFilter.exe" "信息筛选官.exe" >nul
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist InfoFilter.spec del /q InfoFilter.spec

echo.
echo 完成！双击「信息筛选官.exe」即可运行（不需要装 Python）。
pause
