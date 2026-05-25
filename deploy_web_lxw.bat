@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "LXW_GITHUB_USER=lxw"
set "LXW_GITHUB_REPO=stackdefense-lxw"
set "LXW_PAGES_URL=https://%LXW_GITHUB_USER%.github.io/%LXW_GITHUB_REPO%/"

echo.
echo ================================================
echo   《叠层防线》GitHub Pages 部署  [lxw]
echo   公网地址: %LXW_PAGES_URL%
echo ================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo 请先安装 Git: https://git-scm.com/
    pause
    exit /b 1
)

echo 推送到 GitHub（仅需 Git，不必安装 gh）
echo.
echo [1] 打开 https://github.com/new 创建空仓库: %LXW_GITHUB_REPO%
echo     不要勾选 Add a README
echo [2] 本脚本会自动 git push
echo [3] 推送后在仓库 Settings - Pages 选 GitHub Actions
echo.

python tools\deploy_github_pages.py
if errorlevel 1 goto fail

echo.
echo 约 5~15 分钟后访问: %LXW_PAGES_URL%
start "" "https://github.com/%LXW_GITHUB_USER%/%LXW_GITHUB_REPO%/actions"
goto done

:fail
echo 详见 DEPLOY_LXW.txt ；用户名不是 lxw 请改 LXW_GITHUB_USER
pause
exit /b 1

:done
pause
exit /b 0
