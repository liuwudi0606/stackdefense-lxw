@echo off

chcp 65001 >nul

cd /d "%~dp0"

if not exist "build\web\index.html" (

    echo 请先运行 build_web.bat 构建网页版。

    pause

    exit /b 1

)

if not exist "build\web\cdn\0.9.3\pythons.js" (

    echo 首次预览需下载 Python 运行时（约 20MB）...

    python tools\vendor_web_cdn.py

    if errorlevel 1 pause & exit /b 1

)

python tools\patch_web_index.py

echo.

echo 启动预览服务器（带 wasm 必需的安全头）...

echo 浏览器打开 http://localhost:8000/  （全屏游戏，推荐）
echo 调试终端: http://localhost:8000/#debug
echo 若仍是旧版: F12 - 应用 - 清除 localhost 网站数据 - 再 Ctrl+F5

echo.

python tools\serve_web.py 8000

pause

