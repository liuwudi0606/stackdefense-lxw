@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 《叠层防线》网页版构建（pygbag）...
python -m pip install -r requirements.txt pygbag soundfile -q
if not exist "assets\sprites\base.png" (
    echo 生成贴图...
    python tools\gen_sprites.py
)
if not exist "assets\fonts\NotoSansSC-Regular.otf" (
    echo 下载中文字体...
    python tools\fetch_font.py
)
if not exist "assets\sounds\click.wav" (
    python -c "from game.audio import ensure_sounds; ensure_sounds()"
)
python -c "from game.audio import ensure_ogg_sounds; ensure_ogg_sounds()"
echo 正在打包 WASM，首次可能需数分钟...
set PYTHONUTF8=1
python -m pygbag --build --width 960 --height 640 --app_name stackdefense --template web/default.tmpl .
python tools\patch_web_index.py
python tools\ensure_web_headers.py
echo 下载浏览器用 Python 运行时（约 20MB，仅首次）...
python tools\vendor_web_cdn.py
if errorlevel 1 (
    echo 构建失败。
    pause
    exit /b 1
)
echo.
echo 完成。本地预览请双击: preview_web.bat
echo （不要用 python -m http.server，缺少 wasm 所需响应头）
echo.
echo 将 build\web 目录上传到 GitHub Pages / itch.io HTML 即可分享给朋友。
pause
