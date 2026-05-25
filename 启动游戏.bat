@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动《叠层防线》...
python -m pip install -r requirements.txt -q 2>nul
if not exist "assets\sprites\base.png" (
    echo 首次运行，生成像素贴图...
    python tools\gen_sprites.py
)
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败。请确认已安装 Python 3.10+ 并加入 PATH。
    pause
)
