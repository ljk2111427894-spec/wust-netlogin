@echo off
chcp 65001 >nul
title 校园网自动登录程序 Release 打包工具

cd /d "%~dp0"

echo ========================================================
echo       正在生成 CampusNetLogin Release 发布安装包
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 系统中未找到 Python 环境，请先安装 Python。
    pause
    exit /b 1
)

python build_release.py
if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  [成功] Release 安装包与便携包已成功生成！
    echo  产物位于: %~dp0release\
    echo ========================================================
    explorer "%~dp0release"
) else (
    echo [错误] 打包过程出现异常，请检查上方报错输出。
)

pause
