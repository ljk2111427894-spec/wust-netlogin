@echo off
chcp 65001 >nul
title 校园网自动登录程序 - 一键推送到 GitHub

cd /d "%~dp0"

echo ========================================================
echo       WUST 校园网自动登录程序 - GitHub 一键推送
echo ========================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 系统中未找到 Git 工具，请先安装 Git。
    pause
    exit /b 1
)

echo [1/3] 检查代码与文件状态...
git status -s

echo.
echo [2/3] 正在暂存并提交变更...
git add .
set /p commit_msg="请输入提交说明 (直接回车默认: update): "
if "%commit_msg%"=="" set commit_msg=update

git commit -m "%commit_msg%"

echo.
echo [3/3] 正在推送到 GitHub (origin main)...
git push origin main
if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  [成功] 已成功推送到 GitHub 仓库！
    echo  地址: https://github.com/ljk2111427894-spec/wust-netlogin
    echo ========================================================
) else (
    echo.
    echo [提示] 推送失败，请检查网络连接或 GitHub 授权。
)

pause
