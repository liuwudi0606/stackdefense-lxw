"""推送到 GitHub，由 Actions 构建并发布到 GitHub Pages（仅需 Git，gh 可选）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_USER = "lxw"
DEFAULT_REPO = "stackdefense-lxw"


def _run(cmd: list[str], *, quiet: bool = False, **kwargs) -> int:
    if not quiet:
        print("+", " ".join(cmd))
    try:
        return subprocess.run(cmd, cwd=str(ROOT), **kwargs).returncode
    except FileNotFoundError:
        return 127


def pages_url(user: str, repo: str) -> str:
    return f"https://{user}.github.io/{repo}/"


def write_deploy_info(user: str, repo: str, ok: bool, note: str = "") -> None:
    url = pages_url(user, repo)
    lines = [
        "《叠层防线》GitHub Pages 部署（lxw）",
        "=" * 40,
        f"公网地址: {url}",
        f"GitHub 仓库: https://github.com/{user}/{repo}",
        f"状态: {'已推送，等待 Actions 构建' if ok else '未完成'}",
        "",
        "分享给朋友:",
        f"  {url}",
        "",
        "首次使用请在 GitHub 仓库设置:",
        "  Settings → Pages → Build and deployment → Source: GitHub Actions",
        "",
        "查看构建进度:",
        f"  https://github.com/{user}/{repo}/actions",
        "",
        "重新部署: 双击 deploy_web_lxw.bat",
        "本地预览: 双击 preview_web.bat",
    ]
    if note:
        lines.extend(["", note])
    out = ROOT / "DEPLOY_LXW.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已保存 {out}")


def manual_setup_note(user: str, repo: str) -> str:
    origin = f"https://github.com/{user}/{repo}.git"
    return (
        "未安装 GitHub CLI (gh) 时，请先在网页创建空仓库:\n"
        f"  https://github.com/new  仓库名填 {repo}，不要勾选 README\n"
        "然后在项目目录执行:\n"
        f"  git remote add origin {origin}\n"
        "  git add -A\n"
        '  git commit -m "deploy: GitHub Pages (lxw)"\n'
        "  git push -u origin main\n"
        "\n或安装 gh 后重新运行 deploy_web_lxw.bat:\n"
        "  https://cli.github.com/"
    )


def ensure_git_repo() -> bool:
    if (ROOT / ".git").is_dir():
        return True
    return _run(["git", "init", "-b", "main"]) == 0


def get_remote_url() -> str | None:
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def ensure_origin(user: str, repo: str) -> bool:
    url = f"https://github.com/{user}/{repo}.git"
    current = get_remote_url()
    if current:
        if current.rstrip("/").lower().endswith(f"{user}/{repo}.git".lower()):
            return True
        print(f"已有 origin: {current}")
        print(f"若需改为 {url}，请手动: git remote set-url origin {url}")
        return True
    print(f"添加远程仓库 origin → {url}")
    return _run(["git", "remote", "add", "origin", url]) == 0


def ensure_git_identity() -> None:
    for key, default in (("user.name", "lxw"), ("user.email", "lxw@users.noreply.github.com")):
        proc = subprocess.run(
            ["git", "config", key],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if not (proc.stdout or "").strip():
            _run(["git", "config", key, default])


def push_main() -> bool:
    ensure_git_identity()
    _run(["git", "add", "-A"])
    diff = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if diff.stdout.strip():
        if _run(["git", "commit", "-m", "deploy: GitHub Pages (lxw)"]) != 0:
            return False
    else:
        print("没有新的文件改动，继续尝试推送…")
    if _run(["git", "push", "-u", "origin", "main"]) == 0:
        return True
    return _run(["git", "push", "-u", "origin", "master"]) == 0


def create_repo_with_gh(user: str, repo: str) -> bool:
    if not shutil.which("gh"):
        return False
    full = f"{user}/{repo}"
    if _run(["gh", "auth", "status"], quiet=True, capture_output=True) != 0:
        print("已安装 gh 但未登录，请执行: gh auth login")
        return False
    if _run(["gh", "repo", "view", full], quiet=True, capture_output=True) == 0:
        return ensure_origin(user, repo)
    print(f"使用 gh 创建仓库 {full} …")
    return (
        _run(
            [
                "gh",
                "repo",
                "create",
                repo,
                "--public",
                "--source=.",
                "--remote=origin",
                "--push",
                "-d",
                "《叠层防线》网页版",
            ]
        )
        == 0
    )


def trigger_workflow(user: str, repo: str) -> None:
    if not shutil.which("gh"):
        return
    _run(
        [
            "gh",
            "workflow",
            "run",
            "pygbag-pages.yml",
            "--repo",
            f"{user}/{repo}",
        ],
        quiet=True,
    )


def main() -> int:
    user = os.environ.get("LXW_GITHUB_USER", DEFAULT_USER).strip()
    repo = os.environ.get("LXW_GITHUB_REPO", DEFAULT_REPO).strip()

    if not shutil.which("git"):
        print("未找到 git，请安装: https://git-scm.com/")
        write_deploy_info(user, repo, False)
        return 1

    if not ensure_git_repo():
        write_deploy_info(user, repo, False, "git init 失败")
        return 1

    ok = False
    note = ""

    if shutil.which("gh") and not get_remote_url():
        ok = create_repo_with_gh(user, repo)
        if ok:
            write_deploy_info(user, repo, True)
            print(f"\nPages 地址（约 5~15 分钟后）:\n  {pages_url(user, repo)}\n")
            return 0

    if ensure_origin(user, repo):
        ok = push_main()
        if ok:
            trigger_workflow(user, repo)
    else:
        note = "无法配置 git remote"

    if not ok and not note:
        note = manual_setup_note(user, repo)
        if get_remote_url():
            note += (
                "\n\n推送失败常见原因:\n"
                "  1. GitHub 上尚未创建该仓库\n"
                "  2. 未登录 GitHub（可用 GitHub Desktop 或凭据管理器）\n"
                f"  3. 仓库地址应为 https://github.com/{user}/{repo}"
            )

    write_deploy_info(user, repo, ok, note)
    if ok:
        print(f"\nPages 地址（构建约 5~15 分钟后生效）:\n  {pages_url(user, repo)}\n")
        return 0
    print(note or "部署失败")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
