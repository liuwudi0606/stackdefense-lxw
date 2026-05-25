# 《叠层防线》网页版发布说明

本项目使用 [pygbag](https://pygame-web.github.io/) 将 Python / pygame-ce 游戏编译为 WebAssembly，在浏览器中运行。

---

## 环境要求

- Python 3.11+（推荐 3.12）
- 依赖：`pygame-ce`、`pillow`、`pygbag`、`soundfile`（后两者仅构建网页时需要）
- 浏览器：**Chrome** 或 **Edge**（Firefox 对 WASM 支持较弱，不推荐）
- 首次构建会下载/编译 WASM，耗时 **约 10～30 分钟**，请耐心等待

---

## 本地构建

### 方式一：双击脚本（Windows）

```
build_web.bat
```

脚本会自动：

1. 安装依赖
2. 若缺少贴图，运行 `tools/gen_sprites.py`
3. 生成 WAV 音效并转换为 **OGG**（浏览器必需）
4. 执行 `python -m pygbag .`，输出到 `build/web/`

### 方式二：手动命令

```powershell
cd "项目根目录"
pip install -r requirements.txt pygbag soundfile
python tools/gen_sprites.py
python -c "from game.audio import ensure_sounds, ensure_ogg_sounds; ensure_sounds(); ensure_ogg_sounds()"
$env:PYTHONUTF8 = "1"
python -m pygbag .
```

构建成功后，可发布目录为 **`build/web/`**（整个文件夹都要上传）。

---

## 本地预览

**请双击 `preview_web.bat`**（推荐），或：

```powershell
python tools\patch_web_index.py
python tools\vendor_web_cdn.py   # 首次约 20MB，下载 Python WASM 到本地
python tools\serve_web.py 8000
```

浏览器打开：**http://localhost:8000** ，按 **Ctrl+F5** 强刷。

注意：

- **不要用** `python -m http.server`：缺少 wasm 所需的 COOP/COEP 响应头，页面会卡在加载界面
- 首次需从外网拉取约 **20MB** 运行时；`vendor_web_cdn.py` 会缓存到 `build/web/cdn/`，之后可离线预览
- 必须通过 HTTP 访问，不能直接双击 `index.html`
- 加载成功后会进入游戏；若仍卡住，按 F12 看 Console 是否有红色报错

---

## 发布方式

### GitHub Pages（推荐给朋友长期链接）

1. 将项目推送到 GitHub 仓库
2. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**
3. 推送 `main` 或 `master` 分支后，`.github/workflows/pygbag-pages.yml` 会自动构建并部署
4. 部署完成后，Pages 地址一般为：  
   `https://<你的用户名>.github.io/<仓库名>/`

也可在 Actions 页手动 **Run workflow** 触发构建。

### itch.io（HTML 游戏）

构建完成后执行（生成 zip，便于上传）：

```powershell
$env:PYTHONUTF8 = "1"
python -m pygbag . --archive
```

上传 **`build/web.zip`**，项目类型选 **HTML**，勾选 “This file will be played in the browser”。

### 一键公网部署（GitHub Pages · lxw）

双击 **`deploy_web_lxw.bat`**，将代码推送到 GitHub，由 Actions 自动构建并发布。

默认公网地址（用户名 `lxw`、仓库 `stackdefense-lxw`）：

**https://lxw.github.io/stackdefense-lxw/**

首次使用：

1. 安装 [Git](https://git-scm.com/) 与 [GitHub CLI](https://cli.github.com/)
2. 终端执行 `gh auth login` 登录
3. 在仓库 **Settings → Pages → Source** 选择 **GitHub Actions**
4. 若你的 GitHub 用户名不是 `lxw`，编辑 `deploy_web_lxw.bat` 中的 `LXW_GITHUB_USER`

推送后约 5～15 分钟可在上述地址游玩；链接见 **`DEPLOY_LXW.txt`**。

### 其他静态托管

将 **`build/web/`** 目录内所有文件上传到任意支持静态文件的托管（Cloudflare Pages、Netlify、对象存储静态网站等），保证站点根目录能访问到 `index.html`，并配置与 `tools/ensure_web_headers.py` 相同的响应头。

---

## 与桌面版的差异

| 项目 | 桌面版 | 网页版 |
|------|--------|--------|
| 分辨率 | 可调整窗口 / F11 全屏 | 固定 960×640 |
| 音效格式 | `.wav` | `.ogg` |
| 退出 | `sys.exit` | 关闭标签页即可 |
| 存档 | 本地 `save.json` 等 | 浏览器虚拟文件系统（清缓存可能丢失） |
| 调试菜单 F1 | 可用 | 仍可用（开发用） |

环境检测见 `game/platform_util.py` 中的 `is_web()`。

---

## 配置文件说明

- **`pygbag.ini`**：打包时忽略 `tools/`、`build/`、批处理脚本等，减小体积
- **`build/`**：构建产物，已在 `.gitignore` 中，无需提交
- 修改打包排除项时，编辑 `pygbag.ini` 的 `ignoreDirs` / `ignoreFiles`（路径不能含空格）

---

## 常见问题

### 构建报错 `UnicodeDecodeError: gbk`

Windows 默认编码导致。构建脚本已设置 `PYTHONUTF8=1`；若仍失败，在 PowerShell 中先执行：

```powershell
$env:PYTHONUTF8 = "1"
```

并确保 `main.py` 等源码文件为 UTF-8 保存。

### 构建报错 `unsupported format` / 要求 OGG

pygbag 不接受 WAV 作为网页音效。请先运行：

```powershell
python -c "from game.audio import ensure_ogg_sounds; ensure_ogg_sounds()"
```

或重新执行 `build_web.bat`（会自动转换）。

### 构建非常慢或卡住

WASM 编译属正常现象。确保网络可访问 pygbag CDN；可关闭杀毒软件对 `build/web-cache` 的实时扫描后重试。

### 浏览器黑屏 / 无法加载

- 确认使用 `http://localhost` 或 **HTTPS** 线上地址，不要用 `file://`
- 使用 Chrome / Edge，并允许页面运行 WebAssembly
- 打开开发者工具 (F12) 查看 Console 是否有红色报错

### 卡在「加载中」、进度条不动 / 整页灰色

常见原因：

1. 用了 **`python -m http.server`** → 改用 **`preview_web.bat`** 或 `python tools/serve_web.py`
2. **未下载本地运行时** → 运行 `python tools/vendor_web_cdn.py`（需能访问外网 CDN）
3. 控制台 **`BrowserFS not found` / `browserfs.min.js 404`** → 重新运行 `vendor_web_cdn.py`（会从 jsDelivr 拉取 BrowserFS），并 **Ctrl+F5** 强刷
4. 外网 CDN 被墙或极慢 → 本地 `build/web/cdn/` 缓存完成后优先走本地；`serve_web.py` 会对缺失文件自动回源

```powershell
python tools\patch_web_index.py
python tools\vendor_web_cdn.py
python tools\serve_web.py
```

### `--archive` 相关

`--archive` 是**开关参数**，不是文件夹名。正确用法：

```text
python -m pygbag .              # 仅生成 build/web/
python -m pygbag . --archive    # 额外生成 build/web.zip（itch.io）
```

---

## 相关文件

| 文件 | 作用 |
|------|------|
| `build_web.bat` | Windows 一键构建 |
| `pygbag.ini` | pygbag 打包忽略列表 |
| `.github/workflows/pygbag-pages.yml` | GitHub Pages 自动部署 |
| `game/platform_util.py` | 网页 / 桌面环境判断 |
| `game/audio.py` | 音效生成与 OGG 转换 |
| `game/display.py` | 网页固定分辨率 |

更多 pygbag 参数：`python -m pygbag --help`
